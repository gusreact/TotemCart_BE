from decimal import Decimal

from database import get_db_connection


class PaymentRepository:
    def create_pending_order(
        self,
        external_reference: str,
        total: Decimal,
        items: list[dict],
    ) -> None:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO checkout_orders (
                        external_reference, total, currency, status
                    )
                    VALUES (%s, %s, 'ARS', 'pending')
                    RETURNING id;
                    """,
                    (external_reference, total),
                )
                order_id = cursor.fetchone()["id"]

                for item in items:
                    cursor.execute(
                        """
                        INSERT INTO checkout_order_items (
                            order_id, product_id, product_name, quantity, unit_price
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id;
                        """,
                        (
                            order_id,
                            item["id"],
                            item["nombre_es"],
                            item["quantity"],
                            item["precio"],
                        ),
                    )
                    order_item_id = cursor.fetchone()["id"]
                    cursor.executemany(
                        """
                        INSERT INTO checkout_order_ingredients (
                            order_item_id, materia_prima_id, quantity_per_product
                        )
                        VALUES (%s, %s, %s);
                        """,
                        [
                            (
                                order_item_id,
                                ingredient["materia_prima_id"],
                                ingredient["cantidad"],
                            )
                            for ingredient in item["ingredients"]
                        ],
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def set_order_preference(self, external_reference: str, preference_id: str):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE checkout_orders
                    SET preference_id = %s
                    WHERE external_reference = %s;
                    """,
                    (preference_id, external_reference),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("Pending checkout order was not found.")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_order_by_external_reference(self, external_reference: str):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, status, total, currency, payment_id
                    FROM checkout_orders
                    WHERE external_reference = %s;
                    """,
                    (external_reference,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return {
                    "id": row["id"],
                    "status": row["status"],
                    "total": row["total"],
                    "currency": row["currency"],
                    "payment_id": row["payment_id"],
                }
        finally:
            conn.close()

    def record_approved_payment(
        self,
        external_reference: str,
        payment_id: str,
    ) -> bool:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, status, payment_id
                    FROM checkout_orders
                    WHERE external_reference = %s
                    FOR UPDATE;
                    """,
                    (external_reference,),
                )
                order = cursor.fetchone()
                if order is None:
                    conn.rollback()
                    return False

                order_id = order["id"]
                order_status = order["status"]
                existing_payment_id = order["payment_id"]
                if order_status == "paid":
                    if existing_payment_id != payment_id:
                        raise ValueError(
                            "Order was already paid by a different payment."
                        )
                    conn.commit()
                    return True

                cursor.execute(
                    """
                    WITH consumed AS (
                        SELECT ingredient.materia_prima_id,
                               SUM(
                                   ingredient.quantity_per_product * item.quantity
                               ) AS quantity
                        FROM checkout_order_items AS item
                        JOIN checkout_order_ingredients AS ingredient
                          ON ingredient.order_item_id = item.id
                        WHERE item.order_id = %s
                        GROUP BY ingredient.materia_prima_id
                    )
                    UPDATE materias_primas AS material
                    SET stock = GREATEST(0, material.stock - consumed.quantity)
                    FROM consumed
                    WHERE material.id = consumed.materia_prima_id;
                    """,
                    (order_id,),
                )
                updated_material_count = cursor.rowcount
                cursor.execute(
                    """
                    SELECT COUNT(DISTINCT ingredient.materia_prima_id)
                           AS material_count
                    FROM checkout_order_items AS item
                    JOIN checkout_order_ingredients AS ingredient
                      ON ingredient.order_item_id = item.id
                    WHERE item.order_id = %s;
                    """,
                    (order_id,),
                )
                required_material_count = cursor.fetchone()["material_count"]
                if updated_material_count != required_material_count:
                    raise ValueError(
                        "A materia prima for the paid order no longer exists."
                    )

                cursor.execute(
                    """
                    UPDATE checkout_orders
                    SET status = 'paid',
                        payment_id = %s,
                        paid_at = NOW()
                    WHERE id = %s AND status = 'pending';
                    """,
                    (payment_id, order_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("Checkout order status changed unexpectedly.")
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
