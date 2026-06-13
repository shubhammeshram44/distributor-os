import os
import uvicorn

if __name__ == "__main__":
    # Render passes the port dynamically via an environment variable. 
    # We fall back to 8000 for local testing environments.
    port = int(os.getenv("PORT", 8000))
    
    # Binding to "0.0.0.0" allows the app to accept external traffic from Render's proxy router
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"Booting production uvicorn server on {host}:{port}...")
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
