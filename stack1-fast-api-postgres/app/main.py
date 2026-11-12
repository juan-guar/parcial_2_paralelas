from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import time

DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "tasks_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")

def get_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=RealDictCursor,
        connect_timeout=3
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reintentos controlados para inicializar la tabla al arrancar
    retries = 10
    while retries > 0:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS tasks (
                            id SERIAL PRIMARY KEY,
                            title VARCHAR(100) NOT NULL,
                            completed BOOLEAN DEFAULT FALSE
                        );
                    """)
                    conn.commit()
            break
        except Exception:
            retries -= 1
            time.sleep(2)
    yield

app = FastAPI(lifespan=lifespan)

class TaskSchema(BaseModel):
    title: str
    completed: bool = False

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/tasks")
def create_task(task: TaskSchema):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tasks (title, completed) VALUES (%s, %s) RETURNING *;",
                    (task.title, task.completed)
                )
                new_task = cur.fetchone()
                conn.commit()
                return new_task
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks")
def get_tasks():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM tasks;")
                return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskSchema):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tasks SET title = %s, completed = %s WHERE id = %s RETURNING *;",
                    (task.title, task.completed, task_id)
                )
                updated_task = cur.fetchone()
                conn.commit()
                if not updated_task:
                    raise HTTPException(status_code=404, detail="Tarea no encontrada")
                return updated_task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tasks WHERE id = %s RETURNING *;", (task_id,))
                deleted_task = cur.fetchone()
                conn.commit()
                if not deleted_task:
                    raise HTTPException(status_code=404, detail="Tarea no encontrada")
                return {"message": "Tarea eliminada exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))