from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from .database import Base, engine, get_db, SessionLocal
from .models import User, Category, Product, CartItem, Order, OrderItem
from .schemas import RegisterIn, LoginIn, ProductIn, CategoryIn, CartIn, CheckoutIn
from .auth import hash_password, verify_password, create_token, current_user, admin_user

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Loja Profissional API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

ROOT = Path(__file__).resolve().parents[2]
app.mount("/admin", StaticFiles(directory=str(ROOT / "frontend/admin"), html=True), name="admin")
app.mount("/static", StaticFiles(directory=str(ROOT / "frontend")), name="static")

@app.on_event("startup")
def seed():
    db = SessionLocal()
    if not db.query(User).filter_by(email="admin@loja.local").first():
        db.add(User(name="Administrador", email="admin@loja.local", password_hash=hash_password("Admin123!"), is_admin=True))
    if db.query(Category).count() == 0:
        for name, slug in [("Perfumes","perfumes"),("Beleza","beleza"),("Acessórios","acessorios")]:
            db.add(Category(name=name, slug=slug))
        db.commit()
        perfumes = db.query(Category).filter_by(slug="perfumes").first()
        samples = [
            Product(name="Essência Noir", slug="essencia-noir", description="Fragrância marcante para ocasiões especiais.", price=149.90, sale_price=119.90, stock=25, sku="PERF-001", featured=True, category_id=perfumes.id, image_url="https://images.unsplash.com/photo-1541643600914-78b084683601?w=900"),
            Product(name="Aurora Intense", slug="aurora-intense", description="Aroma elegante e moderno.", price=179.90, stock=18, sku="PERF-002", featured=True, category_id=perfumes.id, image_url="https://images.unsplash.com/photo-1594035910387-fea47794261f?w=900"),
            Product(name="Velvet Bloom", slug="velvet-bloom", description="Floral sofisticado para o dia a dia.", price=129.90, stock=32, sku="PERF-003", category_id=perfumes.id, image_url="https://images.unsplash.com/photo-1592945403244-b3fbafd7f539?w=900"),
        ]
        db.add_all(samples)
        db.commit()
    db.close()

@app.get("/")
def home():
    return {"app": "Loja Profissional", "status": "online", "docs": "/docs"}

@app.post("/api/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(func.lower(User.email) == data.email.lower()).first():
        raise HTTPException(409, "E-mail já cadastrado")
    user = User(name=data.name, email=data.email.lower(), password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"token": create_token(user.id), "user": {"id": user.id, "name": user.name, "email": user.email}}

@app.post("/api/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "E-mail ou senha inválidos")
    return {"token": create_token(user.id), "user": {"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin}}

@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin}

@app.get("/api/categories")
def categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name).all()

@app.post("/api/categories")
def create_category(data: CategoryIn, db: Session = Depends(get_db), user=Depends(admin_user)):
    slug = data.name.lower().strip().replace(" ", "-")
    cat = Category(name=data.name, slug=slug)
    db.add(cat); db.commit(); db.refresh(cat)
    return cat

def product_out(p):
    return {"id": p.id, "name": p.name, "slug": p.slug, "description": p.description, "price": p.price, "sale_price": p.sale_price, "stock": p.stock, "image_url": p.image_url, "sku": p.sku, "category_id": p.category_id, "featured": p.featured, "active": p.active}

@app.get("/api/products")
def products(search: str = Query("", max_length=100), category_id: int | None = None, featured: bool | None = None, db: Session = Depends(get_db)):
    q = db.query(Product).filter(Product.active == True)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Product.name.ilike(like), Product.description.ilike(like), Product.sku.ilike(like)))
    if category_id: q = q.filter(Product.category_id == category_id)
    if featured is not None: q = q.filter(Product.featured == featured)
    return [product_out(p) for p in q.order_by(Product.created_at.desc()).all()]

@app.get("/api/products/{product_id}")
def product(product_id: int, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p or not p.active: raise HTTPException(404, "Produto não encontrado")
    return product_out(p)

@app.post("/api/products")
def create_product(data: ProductIn, db: Session = Depends(get_db), user=Depends(admin_user)):
    if db.query(Product).filter_by(sku=data.sku).first(): raise HTTPException(409, "SKU já existe")
    slug = data.name.lower().strip().replace(" ", "-") + "-" + data.sku.lower()
    p = Product(slug=slug, **data.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return product_out(p)

@app.put("/api/products/{product_id}")
def update_product(product_id: int, data: ProductIn, db: Session = Depends(get_db), user=Depends(admin_user)):
    p = db.get(Product, product_id)
    if not p: raise HTTPException(404, "Produto não encontrado")
    for k,v in data.model_dump().items(): setattr(p,k,v)
    db.commit(); db.refresh(p)
    return product_out(p)

@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), user=Depends(admin_user)):
    p = db.get(Product, product_id)
    if not p: raise HTTPException(404, "Produto não encontrado")
    p.active = False; db.commit()
    return {"ok": True}

@app.get("/api/cart")
def get_cart(db: Session = Depends(get_db), user=Depends(current_user)):
    items = db.query(CartItem).filter_by(user_id=user.id).all()
    result=[]; total=0
    for i in items:
        p=i.product
        price=p.sale_price if p.sale_price is not None else p.price
        subtotal=price*i.quantity; total += subtotal
        result.append({"id":i.id,"product":product_out(p),"quantity":i.quantity,"subtotal":round(subtotal,2)})
    return {"items":result,"total":round(total,2)}

@app.post("/api/cart/items")
def add_cart(data: CartIn, db: Session = Depends(get_db), user=Depends(current_user)):
    p=db.get(Product,data.product_id)
    if not p or not p.active: raise HTTPException(404,"Produto não encontrado")
    if data.quantity > p.stock: raise HTTPException(400,"Estoque insuficiente")
    item=db.query(CartItem).filter_by(user_id=user.id,product_id=p.id).first()
    if item: item.quantity=min(item.quantity+data.quantity,p.stock)
    else: db.add(CartItem(user_id=user.id,product_id=p.id,quantity=data.quantity))
    db.commit()
    return {"ok":True}

@app.delete("/api/cart/items/{item_id}")
def remove_cart(item_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
    item=db.query(CartItem).filter_by(id=item_id,user_id=user.id).first()
    if item: db.delete(item); db.commit()
    return {"ok":True}

@app.post("/api/orders")
def checkout(data: CheckoutIn, db: Session=Depends(get_db), user=Depends(current_user)):
    items=db.query(CartItem).filter_by(user_id=user.id).all()
    if not items: raise HTTPException(400,"Carrinho vazio")
    total=0
    order=Order(user_id=user.id,total=0,address=data.address,status="pending")
    db.add(order); db.flush()
    for item in items:
        p=item.product
        if item.quantity > p.stock: raise HTTPException(400,f"Estoque insuficiente: {p.name}")
        price=p.sale_price if p.sale_price is not None else p.price
        total += price*item.quantity
        db.add(OrderItem(order_id=order.id,product_id=p.id,product_name=p.name,unit_price=price,quantity=item.quantity))
        p.stock -= item.quantity
        db.delete(item)
    order.total=round(total,2); db.commit(); db.refresh(order)
    return {"id":order.id,"status":order.status,"total":order.total}

@app.get("/api/orders")
def my_orders(db:Session=Depends(get_db),user=Depends(current_user)):
    orders=db.query(Order).filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    return [{"id":o.id,"status":o.status,"total":o.total,"address":o.address,"created_at":o.created_at.isoformat(),
             "items":[{"name":i.product_name,"price":i.unit_price,"quantity":i.quantity} for i in o.items]} for o in orders]

@app.get("/api/admin/dashboard")
def dashboard(db:Session=Depends(get_db),user=Depends(admin_user)):
    return {"customers":db.query(User).filter(User.is_admin==False).count(),"products":db.query(Product).filter(Product.active==True).count(),
            "orders":db.query(Order).count(),"revenue":round(db.query(func.sum(Order.total)).scalar() or 0,2)}

@app.get("/api/admin/orders")
def admin_orders(db:Session=Depends(get_db),user=Depends(admin_user)):
    orders=db.query(Order).order_by(Order.created_at.desc()).all()
    return [{"id":o.id,"customer":o.user.name,"email":o.user.email,"status":o.status,"total":o.total,"created_at":o.created_at.isoformat()} for o in orders]

@app.put("/api/admin/orders/{order_id}/{status}")
def change_order_status(order_id:int,status:str,db:Session=Depends(get_db),user=Depends(admin_user)):
    allowed={"pending","paid","processing","shipped","delivered","cancelled"}
    if status not in allowed: raise HTTPException(400,"Status inválido")
    o=db.get(Order,order_id)
    if not o: raise HTTPException(404,"Pedido não encontrado")
    o.status=status; db.commit()
    return {"ok":True}
