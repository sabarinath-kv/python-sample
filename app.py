from fastapi import FastAPI

app = FastAPI()

# Root route
@app.get("/")
def root():
    return {"message": "Welcome to the root route!"}

# Route to display info for items
@app.get("/items/")
def items():
    return {"message": "Welcome to the items route!"}

# Route to display info for updating items
@app.get("/items/update/")
def update_item():
    return {"message": "Welcome to the update item route!"}
