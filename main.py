import os
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(title="CEAP Componenti API", version="1.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "CEAP Componenti Backend Running"}

@app.get("/api/health")
def api_health():
    return {"status": "ok"}

# ------------------------------
# Models (API level)
# ------------------------------
class LeadItem(BaseModel):
    code: str = Field(..., description="Codice costruttore o part number")
    quantity: Optional[int] = Field(None, ge=1)
    brand_preference: Optional[str] = None
    target_price: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None

class LeadRequest(BaseModel):
    company: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    items: List[LeadItem] = []
    message: Optional[str] = None
    source: str = "webform"

class ContactRequest(BaseModel):
    company: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    topic: str = Field("Generale", description="Tipo di richiesta")
    message: str

class ChatbotLead(BaseModel):
    company: Optional[str] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    items: List[LeadItem] = []
    channel: str = "chatbot"

# ------------------------------
# Lazy DB helpers
# ------------------------------

def _db_available():
    try:
        from database import db  # type: ignore
        return db is not None
    except Exception:
        return False


def _create_document(collection: str, data: dict) -> Optional[str]:
    try:
        from database import create_document  # type: ignore
        return create_document(collection, data)
    except Exception:
        return None


def _get_documents(collection: str, filt: dict, limit: int):
    try:
        from database import get_documents  # type: ignore
        return get_documents(collection, filt, limit)
    except Exception:
        return []


def _save_uploaded_file(file: UploadFile, bucket: str = "uploads") -> dict:
    content = file.file.read()
    doc = {
        "bucket": bucket,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "blob": content,  # In produzione usare storage esterno o GridFS
    }
    file_id = _create_document("file", doc)
    return {"file_id": file_id, "filename": file.filename, "size": len(content)}

# ------------------------------
# Endpoints
# ------------------------------

@app.post("/api/leads")
async def create_lead(
    company: str = Form(...),
    name: str = Form(...),
    email: EmailStr = Form(...),
    phone: Optional[str] = Form(None),
    message: Optional[str] = Form(None),
    items_json: Optional[str] = Form(None, description="JSON array of LeadItem"),
    file: Optional[UploadFile] = File(None),
):
    items: List[LeadItem] = []
    if items_json:
        import json
        raw = json.loads(items_json)
        items = [LeadItem(**it) for it in raw]

    file_meta = None
    if file is not None:
        file_meta = _save_uploaded_file(file, bucket="leads")

    payload = LeadRequest(
        company=company,
        name=name,
        email=email,
        phone=phone,
        items=items,
        message=message,
        source="webform",
    )
    doc = payload.model_dump()
    if file_meta:
        doc["attachment"] = file_meta

    _id = _create_document("lead", doc)
    if _id is None and _db_available() is False:
        # Accetta comunque la richiesta anche senza DB, utile per demo
        return {"ok": True, "id": None, "warning": "DB non configurato: richiesta ricevuta ma non salvata."}
    if _id is None:
        raise HTTPException(status_code=500, detail="Errore nel salvataggio della richiesta")

    return {"ok": True, "id": _id}


@app.post("/api/contact")
async def create_contact(
    company: str = Form(...),
    name: str = Form(...),
    email: EmailStr = Form(...),
    phone: Optional[str] = Form(None),
    topic: Optional[str] = Form("Generale"),
    message: str = Form(...),
    file: Optional[UploadFile] = File(None),
):
    file_meta = None
    if file is not None:
        file_meta = _save_uploaded_file(file, bucket="contacts")

    payload = ContactRequest(company=company, name=name, email=email, phone=phone, topic=topic, message=message)
    doc = payload.model_dump()
    if file_meta:
        doc["attachment"] = file_meta

    _id = _create_document("contactmessage", doc)
    if _id is None and _db_available() is False:
        return {"ok": True, "id": None, "warning": "DB non configurato: richiesta ricevuta ma non salvata."}
    if _id is None:
        raise HTTPException(status_code=500, detail="Errore nel salvataggio del messaggio")

    return {"ok": True, "id": _id}


@app.get("/api/components")
def list_components(
    type: Optional[str] = None,
    mount: Optional[str] = None,
    package: Optional[str] = None,
    brand: Optional[str] = None,
    limit: int = 50,
):
    filt = {}
    if type: filt["type"] = type
    if mount: filt["mount"] = mount
    if package: filt["package"] = package
    if brand: filt["brand"] = brand

    items = _get_documents("componentitem", filt, limit)
    if not items or isinstance(items, dict):
        demo = [
            {"code": "BSS138", "brand": "ON Semi", "type": "MOSFET", "mount": "SMD", "package": "SOT-23", "notes": "N-MOSFET 50V"},
            {"code": "LM358", "brand": "Texas Instruments", "type": "IC", "mount": "PTH", "package": "DIP-8", "notes": "Dual op-amp"},
            {"code": "ATmega328P", "brand": "Microchip", "type": "Microcontrollore", "mount": "SMD", "package": "TQFP-32", "notes": "8-bit MCU"},
            {"code": "1N4148", "brand": "Vishay", "type": "Diodo", "mount": "PTH", "package": "DO-35", "notes": "Small signal diode"},
            {"code": "FUS-1206-1A", "brand": "Littelfuse", "type": "Fusibile", "mount": "SMD", "package": "1206", "notes": "Fuse 1A"},
        ]
        return {"items": demo[:limit]}

    for it in items:
        if "_id" in it:
            it["id"] = str(it.get("_id"))
            it.pop("_id", None)
    return {"items": items[:limit]}


@app.get("/api/faq")
def get_faq():
    faq = [
        {"q": "Tempi medi di risposta?", "a": "Generalmente entro 24–48 ore lavorative."},
        {"q": "Tempi di consegna?", "a": "In media 2–3 settimane, variabile in base a brand e disponibilità."},
        {"q": "Posso inviare un file?", "a": "Sì, accettiamo Excel/PDF con codici, quantità e note."},
        {"q": "Gestite componenti obsoleti?", "a": "Sì, ricerchiamo alternative e lotti speciali."},
    ]
    return {"items": faq}


@app.post("/api/chatbot/lead")
async def chatbot_lead(payload: ChatbotLead):
    doc = payload.model_dump()
    _id = _create_document("lead", doc)
    if _id is None and _db_available() is False:
        return {"ok": True, "id": None, "warning": "DB non configurato: richiesta ricevuta ma non salvata."}
    if _id is None:
        raise HTTPException(status_code=500, detail="Errore nel salvataggio della richiesta")
    return {"ok": True, "id": _id}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        from database import db  # type: ignore
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
