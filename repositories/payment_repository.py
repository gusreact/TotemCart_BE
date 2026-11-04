from decimal import Decimal

from database import get_db_connection


class PaymentRepository:
    def update_sale_state(self, order_id: int, state_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE checkout_orders AS sale
                    SET pedido_estado_id = state.id,
                        preparation_at = CASE
                        WHEN state.id = 2 THEN
                            timezone('America/Argentina/Buenos_Aires', NOW())
                        ELSE sale.preparation_at
                    END
                    FROM pedido_estado AS state
                    WHERE sale.id = %s
                      AND state.id = %s
                    RETURNING sale.id, sale.pedido_estado_id, sale.preparation_at,
                              state.descripcion_es, state.descripcion_en;
                    """,
                    (order_id, state_id),
                )
                row = cursor.fetchone()
            conn.commit()
            if row is None:
                return None
            return {
                "id": row["id"],
                "pedido_estado_id": row["pedido_estado_id"],
                "preparation_at": row["preparation_at"],
                "pedido_estado": {
                    "id": row["pedido_estado_id"],
                    "descripcion_es": row["descripcion_es"],
                    "descripcion_en": row["descripcion_en"],
                },
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_sales(self) -> list[dict]:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        sale.id AS order_id,
                        sale.external_reference,
                        sale.pedido_codigo,
                        sale.pedido_estado_id,
                        state.descripcion_es AS estado_descripcion_es,
                        state.descripcion_en AS estado_descripcion_en,
                        sale.preference_id,
                        sale.total,
                        sale.currency,
                        sale.status AS payment_status,
                        sale.payment_id,
                        sale.payer_identification_number,
                        sale.created_at,
                        sale.paid_at,
                        sale.preparation_at,
                        item.id AS order_item_id,
                        item.product_id,
                        item.product_name,
                        item.quantity AS product_quantity,
                        item.unit_price,
                        ingredient.materia_prima_id,
                        material.nombre_es AS materia_prima_nombre_es,
                        material.nombre_en AS materia_prima_nombre_en,
                        ingredient.quantity_per_product
                    FROM checkout_orders AS sale
                    JOIN pedido_estado AS state
                      ON state.id = sale.pedido_estado_id
                    LEFT JOIN checkout_order_items AS item
                      ON item.order_id = sale.id
                    LEFT JOIN checkout_order_ingredients AS ingredient
                      ON ingredient.order_item_id = item.id
                    LEFT JOIN materias_primas AS material
                      ON material.id = ingredient.materia_prima_id
                    ORDER BY sale.created_at DESC, sale.id DESC,
                             item.id, ingredient.materia_prima_id;
                    """
                )
                rows = cursor.fetchall()
        finally:
            conn.close()

        sales_by_id = {}
        items_by_id = {}
        for row in rows:
            sale_id = row["order_id"]
            if sale_id not in sales_by_id:
                sales_by_id[sale_id] = {
                    "id": sale_id,
                    "external_reference": row["external_reference"],
                    "pedido_codigo": row["pedido_codigo"],
                    "pedido_estado_id": row["pedido_estado_id"],
                    "pedido_estado": {
                        "id": row["pedido_estado_id"],
                        "descripcion_es": row["estado_descripcion_es"],
                        "descripcion_en": row["estado_descripcion_en"],
                    },
                    "preference_id": row["preference_id"],
                    "total": row["total"],
                    "currency": row["currency"],
                    "payment_status": row["payment_status"],
                    "payment_id": row["payment_id"],
                    "payer_identification_number": row[
                        "payer_identification_number"
                    ],
                    "created_at": row["created_at"],
                    "paid_at": row["paid_at"],
                    "preparation_at": row["preparation_at"],
                    "items": [],
                }

            order_item_id = row["order_item_id"]
            if order_item_id is None:
                continue
            item_key = (sale_id, order_item_id)
            if item_key not in items_by_id:
                item = {
                    "id": order_item_id,
                    "product_id": row["product_id"],
                    "product_name": row["product_name"],
                    "quantity": row["product_quantity"],
                    "unit_price": row["unit_price"],
                    "ingredients": [],
                }
                items_by_id[item_key] = item
                sales_by_id[sale_id]["items"].append(item)

            materia_prima_id = row["materia_prima_id"]
            if materia_prima_id is not None:
                items_by_id[item_key]["ingredients"].append(
                    {
                        "materia_prima_id": materia_prima_id,
                        "nombre_es": row["materia_prima_nombre_es"],
                        "nombre_en": row["materia_prima_nombre_en"],
                        "quantity_per_product": row["quantity_per_product"],
                    }
                )

        return list(sales_by_id.values())

    def get_sale_by_code(self, pedido_codigo: str) -> dict | None:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        sale.pedido_estado_id,
                        state.descripcion_es AS estado_descripcion_es,
                        state.descripcion_en AS estado_descripcion_en,
                        sale.preparation_at,
                        item.product_id,
                        item.product_name,
                        item.quantity AS product_quantity
                    FROM checkout_orders AS sale
                    JOIN pedido_estado AS state
                      ON state.id = sale.pedido_estado_id
                    LEFT JOIN checkout_order_items AS item
                      ON item.order_id = sale.id
                    WHERE sale.pedido_codigo = %s
                    ORDER BY item.id;
                    """,
                    (pedido_codigo,),
                )
                rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            return None

        first_row = rows[0]
        return {
            "pedido_estado_id": first_row["pedido_estado_id"],
            "pedido_estado": {
                "id": first_row["pedido_estado_id"],
                "descripcion_es": first_row["estado_descripcion_es"],
                "descripcion_en": first_row["estado_descripcion_en"],
            },
            "preparation_at": first_row["preparation_at"],
            "items": [
                {
                    "product_id": row["product_id"],
                    "product_name": row["product_name"],
                    "quantity": row["product_quantity"],
                }
                for row in rows
                if row["product_id"] is not None
            ],
        }

    def create_pending_order(
        self,
        external_reference: str,
        pedido_codigo: str,
        total: Decimal,
        items: list[dict],
    ) -> None:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO checkout_orders (
                        external_reference,
                        pedido_codigo,
                        pedido_estado_id,
                        total,
                        currency,
                        status
                    )
                    VALUES (%s, %s, 1, %s, 'ARS', 'pending')
                    RETURNING id;
                    """,
                    (external_reference, pedido_codigo, total),
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
        payer_identification_number: str | None = None,
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
                    cursor.execute(
                        """
                        UPDATE checkout_orders
                        SET payer_identification_number = COALESCE(
                                payer_identification_number, %s
                            )
                        WHERE id = %s;
                        """,
                        (
                            payer_identification_number,
                            order_id,
                        ),
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
                        payer_identification_number = %s,
                        paid_at = timezone(
                            'America/Argentina/Buenos_Aires',
                            NOW()
                        )
                    WHERE id = %s AND status = 'pending';
                    """,
                    (
                        payment_id,
                        payer_identification_number,
                        order_id,
                    ),
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
