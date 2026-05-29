from backend.services.api.main import app
for route in app.routes:
    print(f"{route.path} [{','.join(route.methods) if hasattr(route, 'methods') else 'MOUNT'}]")
