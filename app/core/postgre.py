import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid
from psycopg2.pool import ThreadedConnectionPool
import uuid

# Register UUID adapter for psycopg2 to automatically adapt/convert UUID objects
register_uuid()
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, List, Dict, Any
import json
from app.core.config import settings

def adapt_value(key: str, val: Any) -> Any:
    if isinstance(val, dict):
        return json.dumps(val)
    elif isinstance(val, list):
        if (len(val) > 0 and any(isinstance(x, dict) for x in val)) or key in {"question", "body", "result", "payload", "layout_json"}:
            return json.dumps(val)
    return val

def serialize_value(val: Any) -> Any:
    if isinstance(val, uuid.UUID):
        return str(val)
    elif isinstance(val, Decimal):
        return float(val)
    elif isinstance(val, (datetime, date)):
        return val.isoformat()
    elif isinstance(val, list):
        return [serialize_value(x) for x in val]
    elif isinstance(val, dict):
        return {k: serialize_value(v) for k, v in val.items()}
    return val

class PostgreClient:
    _pool: Optional[ThreadedConnectionPool] = None

    def __init__(self, *args, **kwargs):
        self._init_pool()

    def _init_pool(self):
        if PostgreClient._pool is None:
            if settings.DATABASE_URL:
                try:
                    # Maintain up to 20 connections in the pool
                    PostgreClient._pool = ThreadedConnectionPool(
                        1, 20,
                        dsn=settings.DATABASE_URL,
                        connect_timeout=3
                    )
                    print("[DB Backend] Pool initialized successfully using DATABASE_URL")
                except Exception as e:
                    print(f"[DB Backend] Failed to initialize connection pool: {e}")

    def table(self, table_name: str):
        if PostgreClient._pool is None:
            self._init_pool()
        return TableBuilder(table_name, self._pool)

class TableBuilder:
    def __init__(self, table_name: str, pool: ThreadedConnectionPool):
        self.table_name = table_name
        self.pool = pool
        self.columns = "*"
        self.filters = []  # list of tuples: (column, operator, value)
        self.orders = []   # list of tuples: (column, direction)
        self.limit_val = None
        self.operation = "SELECT"  # SELECT, INSERT, UPDATE, DELETE, UPSERT
        self.data = None
        self.on_conflict_cols = []

    def select(self, columns: str):
        self.columns = columns
        return self

    def eq(self, column: str, value: Any):
        self.filters.append((column, "=", value))
        return self

    def gte(self, column: str, value: Any):
        self.filters.append((column, ">=", value))
        return self

    def in_(self, column: str, values: List[Any]):
        if not values:
            self.filters.append(("1", "=", "0"))
        else:
            self.filters.append((column, "IN", tuple(values)))
        return self

    def order(self, column: str, desc: bool = False):
        direction = "DESC" if desc else "ASC"
        self.orders.append((column, direction))
        return self

    def limit(self, count: int):
        self.limit_val = count
        return self

    def insert(self, data: Any):
        self.operation = "INSERT"
        self.data = data
        return self

    def update(self, data: Any):
        self.operation = "UPDATE"
        self.data = data
        return self

    def delete(self):
        self.operation = "DELETE"
        return self

    def upsert(self, data: Any, on_conflict: str):
        self.operation = "UPSERT"
        self.data = data
        self.on_conflict_cols = [col.strip() for col in on_conflict.split(",") if col.strip()]
        return self

    def execute(self):
        if not self.pool:
            raise Exception("Database connection pool is not initialized")
            
        conn = self.pool.getconn()
        conn.autocommit = True
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                result_rows = []
                
                if self.operation == "SELECT":
                    query_parts = [f"SELECT * FROM {self.table_name}"]
                    params = []

                    # WHERE
                    where_clauses = []
                    for col, op, val in self.filters:
                        where_clauses.append(f"{col} {op} %s")
                        params.append(val)

                    if where_clauses:
                        query_parts.append("WHERE " + " AND ".join(where_clauses))

                    # ORDER BY
                    if self.orders:
                        order_strs = [f"{col} {direction}" for col, direction in self.orders]
                        query_parts.append("ORDER BY " + ", ".join(order_strs))

                    # LIMIT
                    if self.limit_val is not None:
                        query_parts.append("LIMIT %s")
                        params.append(self.limit_val)

                    sql = " ".join(query_parts)
                    cur.execute(sql, params)
                    raw_rows = [dict(r) for r in cur.fetchall()]
                    
                    # Intercept nested selects
                    result_rows = self._fetch_relations(raw_rows, cur)
                    
                elif self.operation == "INSERT":
                    records = self.data if isinstance(self.data, list) else [self.data]
                    for record in records:
                        keys = list(record.keys())
                        values = [adapt_value(k, record[k]) for k in keys]
                        placeholders = ", ".join(["%s"] * len(keys))
                        columns_str = ", ".join(keys)
                        
                        sql = f"INSERT INTO {self.table_name} ({columns_str}) VALUES ({placeholders}) RETURNING *"
                        cur.execute(sql, values)
                        res_row = cur.fetchone()
                        if res_row:
                            result_rows.append(dict(res_row))

                elif self.operation == "UPSERT":
                    if not self.on_conflict_cols:
                        raise ValueError("upsert requires on_conflict columns")

                    records = self.data if isinstance(self.data, list) else [self.data]
                    for record in records:
                        keys = list(record.keys())
                        values = [adapt_value(k, record[k]) for k in keys]
                        placeholders = ", ".join(["%s"] * len(keys))
                        columns_str = ", ".join(keys)
                        conflict_str = ", ".join(self.on_conflict_cols)
                        update_keys = [k for k in keys if k not in self.on_conflict_cols]

                        if update_keys:
                            update_str = ", ".join([f"{k} = EXCLUDED.{k}" for k in update_keys])
                            sql = (
                                f"INSERT INTO {self.table_name} ({columns_str}) VALUES ({placeholders}) "
                                f"ON CONFLICT ({conflict_str}) DO UPDATE SET {update_str} RETURNING *"
                            )
                        else:
                            sql = (
                                f"INSERT INTO {self.table_name} ({columns_str}) VALUES ({placeholders}) "
                                f"ON CONFLICT ({conflict_str}) DO NOTHING RETURNING *"
                            )

                        cur.execute(sql, values)
                        res_row = cur.fetchone()
                        if res_row:
                            result_rows.append(dict(res_row))
                            
                elif self.operation == "UPDATE":
                    keys = list(self.data.keys())
                    values = [adapt_value(k, self.data[k]) for k in keys]
                    set_clauses = [f"{k} = %s" for k in keys]
                    set_str = ", ".join(set_clauses)
                    
                    query_parts = [f"UPDATE {self.table_name} SET {set_str}"]
                    where_clauses = []
                    where_params = []
                    for col, op, val in self.filters:
                        where_clauses.append(f"{col} {op} %s")
                        where_params.append(val)

                    if where_clauses:
                        query_parts.append("WHERE " + " AND ".join(where_clauses))
                        
                    query_parts.append("RETURNING *")
                    sql = " ".join(query_parts)
                    params = values + where_params
                    
                    cur.execute(sql, params)
                    result_rows = [dict(r) for r in cur.fetchall()]
                    
                elif self.operation == "DELETE":
                    query_parts = [f"DELETE FROM {self.table_name}"]
                    params = []
                    
                    where_clauses = []
                    for col, op, val in self.filters:
                        where_clauses.append(f"{col} {op} %s")
                        params.append(val)

                    if where_clauses:
                        query_parts.append("WHERE " + " AND ".join(where_clauses))
                        
                    query_parts.append("RETURNING *")
                    sql = " ".join(query_parts)
                    
                    cur.execute(sql, params)
                    result_rows = [dict(r) for r in cur.fetchall()]

                serialized_data = [serialize_value(row) for row in result_rows]
                return type('Response', (), {'data': serialized_data, 'error': None})
                
        finally:
            if self.pool and conn:
                self.pool.putconn(conn)

    def _fetch_relations(self, rows: List[Dict[str, Any]], cur) -> List[Dict[str, Any]]:
        if not rows:
            return rows

        select_cols = self.columns.lower()

        # CASE 1: courses -> chapters -> lessons
        if self.table_name == "courses" and "chapters" in select_cols:
            for row in rows:
                course_id = row.get("id")
                if course_id:
                    cur.execute("SELECT * FROM chapters WHERE course_id = %s ORDER BY sort_order ASC", (course_id,))
                    chapters = [dict(r) for r in cur.fetchall()]
                    
                    for chapter in chapters:
                        ch_id = chapter.get("id")
                        if ch_id:
                            cur.execute("SELECT * FROM lessons WHERE chapter_id = %s ORDER BY sort_order ASC", (ch_id,))
                            lessons = [dict(r) for r in cur.fetchall()]
                            chapter["lessons"] = [serialize_value(l) for l in lessons]
                            
                    row["chapters"] = [serialize_value(c) for c in chapters]

        # CASE 2: registrations -> students -> parents
        elif self.table_name == "registrations" and "parents" in select_cols:
            for row in rows:
                student_id = row.get("student_id")
                if student_id:
                    cur.execute("SELECT name, parent_id FROM students WHERE id = %s", (student_id,))
                    student_row = cur.fetchone()
                    if student_row:
                        student = dict(student_row)
                        parent_id = student.get("parent_id")
                        if parent_id:
                            cur.execute("SELECT email, whatsapp_number FROM parents WHERE id = %s", (parent_id,))
                            parent_row = cur.fetchone()
                            student["parents"] = dict(parent_row) if parent_row else None
                        else:
                            student["parents"] = None
                        row["students"] = serialize_value(student)
                    else:
                        row["students"] = None

        # CASE 3: registrations -> classes + students
        elif self.table_name == "registrations" and "classes" in select_cols:
            for row in rows:
                class_id = row.get("class_id")
                student_id = row.get("student_id")
                
                if class_id:
                    cur.execute("SELECT display_name, subtitle, base_price FROM classes WHERE id = %s", (class_id,))
                    class_row = cur.fetchone()
                    row["classes"] = dict(class_row) if class_row else None
                    
                if student_id:
                    cur.execute("SELECT name FROM students WHERE id = %s", (student_id,))
                    student_row = cur.fetchone()
                    row["students"] = dict(student_row) if student_row else None

        # CASE 4: catalog_layout -> classes (with dynamic quota from courses)
        elif self.table_name == "catalog_layout" and "classes" in select_cols:
            for row in rows:
                batch_id = row.get("batch_id")
                if batch_id:
                    cur.execute("SELECT * FROM classes WHERE id = %s", (batch_id,))
                    class_row = cur.fetchone()
                    if class_row:
                        cls = dict(class_row)
                        cls["status"] = cls.get("status") or "open"
                        
                        # Count active enrollments for this class
                        cur.execute(
                            "SELECT COUNT(*) as cnt FROM enrollments "
                            "WHERE class_id = %s AND status = 'active'",
                            (batch_id,)
                        )
                        enrollment_count = cur.fetchone()["cnt"] or 0
                        cls["filled_quota"] = enrollment_count
                        
                        # Calculate dynamic quota from active programs
                        cur.execute(
                            "SELECT COALESCE(SUM(p.max_quota), 0) as total_max "
                            "FROM programs p "
                            "JOIN class_programs cp ON cp.program_id = p.id "
                            "WHERE cp.class_id = %s AND p.is_active = true",
                            (batch_id,)
                        )
                        total_max_row = cur.fetchone()
                        total_max = total_max_row["total_max"] if total_max_row else 0
                        if total_max == 0:
                            total_max = cls.get("max_quota") or 0
                        cls["max_quota"] = total_max
                        
                        row["classes"] = cls
                    else:
                        row["classes"] = None
                else:
                    row["classes"] = None

        return rows

db = PostgreClient()
# Legacy alias for compatibility
supabase = db
