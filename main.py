import os
import json
import urllib.request
import shutil
import jwt
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import SessionLocal, engine
from datetime import date, timedelta, datetime
import models

SECRET_KEY = "merve_safa_alparslan_erp_secret"

os.makedirs("uploads", exist_ok=True)
app = FastAPI(title="Merve Safa Alparslan Hukuk ERP API", version="5.5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@app.get("/")
def ana_sayfa():
    return FileResponse("İNDEX.HTML")

# --- ŞEMALAR ---
class ChatRequest(BaseModel): message: str
class PetitionRequest(BaseModel): dosya_no: str; dilekce_turu: str; detay: str = ""
class LoginRequest(BaseModel): username: str; password: str
class TodoCreate(BaseModel): task: str; detay: str = ""
class ClientCaseCreate(BaseModel): tc_kimlik: str; ad_soyad: str; telefon: str = ""; dosya_no: str; karsi_taraf: str; tur: str
class CaseUpdate(BaseModel): durum: str; karsi_taraf: str
class ExpenseCreate(BaseModel): kalem: str; kategori: str; tutar: float

# --- GİRİŞ VE ÇİFT ROL DOĞRULAMA (AVUKAT & MÜVEKKİL) ---
@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # Önce Avukat tablosuna bak
    user = db.query(models.User).filter(models.User.username == req.username).first()
    if user and user.password_hash == req.password:
        token = jwt.encode({"sub": user.username, "role": "Avukat", "ad": user.ad_soyad}, SECRET_KEY, algorithm="HS256")
        return {"token": token, "role": "Avukat", "ad_soyad": user.ad_soyad}
    
    # Bulamazsa Müvekkil tablosuna (TC ile) bak
    client = db.query(models.Client).filter(models.Client.tc_kimlik == req.username).first()
    if client and client.password == req.password:
        token = jwt.encode({"sub": client.tc_kimlik, "role": "Müvekkil", "ad": client.ad_soyad, "id": client.id}, SECRET_KEY, algorithm="HS256")
        return {"token": token, "role": "Müvekkil", "ad_soyad": client.ad_soyad, "client_id": client.id}
        
    raise HTTPException(status_code=401, detail="Kimlik bilgileri geçersiz.")

# --- MÜVEKKİL PORTALI ÖZEL VERİ ERİŞİM UCU ---
@app.get("/api/client-portal/{client_id}/dashboard")
def get_client_portal_data(client_id: int, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client: raise HTTPException(status_code=404, detail="Müvekkil bulunamadı.")
    
    hesap = client.account
    dosyalar_listesi = []
    for c in client.cases:
        dosyalar_listesi.append({
            "id": c.id, "dosya_no": c.dosya_no, "tur": c.tur.value, "durum": c.durum, "karsi_taraf": c.karsi_taraf,
            "asamalar": [{"tarih": s.tarih.strftime("%d.%m.%Y"), "aciklama": s.aciklama} for s in c.stages],
            "evraklar": [{"ad": d.evrak_adi, "yol": d.dosya_yolu} for d in c.documents]
        })
        
    return {
        "profil": {"ad": client.ad_soyad, "tc": client.tc_kimlik, "tel": client.telefon},
        "finans": {"toplam": hesap.toplam_borc if hesap else 0, "odenen": hesap.odenen if hesap else 0, "kalan": (hesap.toplam_borc - hesap.odenen) if hesap else 0},
        "dosyalar": files_list if (files_list := dosyalar_listesi) else []
    }

# --- C.R.U.D. GÜNCELLEME VE SİLME ENDPOINTLERİ ---
@app.delete("/api/cases/{case_id}")
def delete_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(models.CaseFile).filter(models.CaseFile.id == case_id).first()
    if not case: raise HTTPException(status_code=404)
    db.delete(case); db.commit()
    return {"mesaj": "Dosya sistemden kalıcı olarak silindi."}

@app.put("/api/cases/{case_id}")
def update_case(case_id: int, req: CaseUpdate, db: Session = Depends(get_db)):
    case = db.query(models.CaseFile).filter(models.CaseFile.id == case_id).first()
    if not case: raise HTTPException(status_code=404)
    case.durum = req.durum
    case.karsi_taraf = req.karsi_taraf
    db.commit()
    return {"mesaj": "Dosya güncellendi."}

@app.post("/api/expenses")
def create_expense(req: ExpenseCreate, db: Session = Depends(get_db)):
    yeni_gider = models.OfficeExpense(kalem=req.kalem, kategori=req.kategori, tutar=req.tutar)
    db.add(yeni_gider); db.commit()
    return {"mesaj": "Gider kaydedildi."}

@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    exp = db.query(models.OfficeExpense).filter(models.OfficeExpense.id == expense_id).first()
    if not exp: raise HTTPException(status_code=404)
    db.delete(exp); db.commit()
    return {"mesaj": "Gider kaydı silindi."}

# --- MEVCUT DİĞER CODELARIN MODÜLER ENTEGRASYONU ---
@app.post("/api/add-client-case")
def add_client_case(data: ClientCaseCreate, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(models.Client.tc_kimlik == data.tc_kimlik).first()
    if not client:
        client = models.Client(tc_kimlik=data.tc_kimlik, ad_soyad=data.ad_soyad, telefon=data.telefon)
        db.add(client); db.commit(); db.refresh(client)
    try: case_type = models.CaseType(data.tur)
    except: case_type = models.CaseType.DAVA
    yeni_dosya = models.CaseFile(dosya_no=data.dosya_no, karsi_taraf=data.karsi_taraf, tur=case_type, durum="Süreç Başladı", client_id=client.id)
    db.add(yeni_dosya)
    if not client.account: db.add(models.Account(client_id=client.id, toplam_borc=5000.0, odenen=0.0))
    db.add(models.CaseStage(aciklama="Dosya ilk kaydı yapıldı.", case_id=yeni_dosya.id))
    db.commit()
    return {"mesaj": "Kayıt Başarıyla Oluşturuldu"}

@app.get("/api/dashboard-stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    return {"aktif_muvekkil": db.query(models.Client).count(), "acik_dava": db.query(models.CaseFile).filter(models.CaseFile.is_closed == False, models.CaseFile.tur == models.CaseType.DAVA).count(), "bekleyen_gorev": db.query(models.TodoItem).filter(models.TodoItem.is_completed == False).count(), "bu_hafta_durusma": db.query(models.Hearing).filter(models.Hearing.tarih >= date.today(), models.Hearing.tarih <= date.today() + timedelta(days=7)).count()}

@app.get("/api/all-cases")
def all_cases(db: Session = Depends(get_db)): return [{"id": c.id, "dosya_no": c.dosya_no, "muvekkil": c.owner.ad_soyad, "karsi_taraf": c.karsi_taraf, "tur": c.tur.value, "durum": c.durum} for c in db.query(models.CaseFile).filter(models.CaseFile.is_closed == False).all()]

@app.get("/api/closed-cases")
def closed_cases(db: Session = Depends(get_db)): return [{"id": c.id, "dosya_no": c.dosya_no, "muvekkil": c.owner.ad_soyad, "tur": c.tur.value, "durum": c.durum, "kapanis": c.kapanis_tarihi.strftime("%d.%m.%Y") if c.kapanis_tarihi else "-"} for c in db.query(models.CaseFile).filter(models.CaseFile.is_closed == True).all()]

@app.get("/api/clients")
def get_clients(db: Session = Depends(get_db)): return [{"id": c.id, "tc_kimlik": c.tc_kimlik, "ad_soyad": c.ad_soyad, "telefon": c.telefon, "eposta": c.eposta} for c in db.query(models.Client).filter(models.Client.kurumsal_mi == False).all()]

@app.get("/api/corporate-clients")
def get_corporate_clients(db: Session = Depends(get_db)): return [{"id": c.id, "vergi_no": c.tc_kimlik, "unvan": c.ad_soyad, "telefon": c.telefon, "eposta": c.eposta} for c in db.query(models.Client).filter(models.Client.kurumsal_mi == True).all()]

@app.get("/api/hearings")
def get_hearings(db: Session = Depends(get_db)): return [{"tarih": h.tarih.strftime("%d.%m.%Y"), "saat": h.saat or "10:00", "mahkeme": h.mahkeme, "dosya_no": h.case_file.dosya_no, "muvekkil": h.case_file.owner.ad_soyad, "case_id": h.case_id} for h in db.query(models.Hearing).order_by(models.Hearing.tarih).all()]

@app.get("/api/finance")
def get_finance(db: Session = Depends(get_db)):
    accounts = db.query(models.Account).all()
    giderler = db.query(models.OfficeExpense).all()
    return {
        "liste": [{"muvekkil": a.client.ad_soyad, "toplam": a.toplam_borc, "odenen": a.odenen, "kalan": a.toplam_borc - a.odenen} for a in accounts],
        "gider_listesi": [{"id": g.id, "kalem": g.kalem, "kategori": g.kategori, "tutar": g.tutar, "tarih": g.tarih.strftime("%d.%m.%Y")} for g in giderler],
        "ozet": {"toplam_alacak": sum(a.toplam_borc for a in accounts), "toplam_tahsilat": sum(a.odenen for a in accounts), "net_kalan": sum(a.toplam_borc - a.odenen for a in accounts), "toplam_gider": sum(g.tutar for g in giderler)}
    }

@app.post("/api/todos")
def create_todo(todo: TodoCreate, db: Session = Depends(get_db)):
    db.add(models.TodoItem(task=todo.task, detay=todo.detay)); db.commit()
    return {"mesaj": "Giriş Başarılı"}

@app.get("/api/todos")
def get_todos(db: Session = Depends(get_db)): return [{"id": t.id, "task": t.task, "detay": t.detay, "dosya": t.bagli_dosya_no} for t in db.query(models.TodoItem).filter(models.TodoItem.is_completed == False).all()]

@app.get("/api/todos/archive")
def get_todo_archive(db: Session = Depends(get_db)): return [{"task": t.task, "detay": t.detay, "status": t.status, "eklenme": t.created_at.strftime("%d.%m.%Y"), "bitis": t.completed_at.strftime("%d.%m.%Y") if t.completed_at else "-"} for t in db.query(models.TodoItem).filter(models.TodoItem.is_completed == True).all()]

@app.put("/api/todos/{todo_id}/toggle")
def toggle_todo(todo_id: int, db: Session = Depends(get_db)):
    t = db.query(models.TodoItem).filter(models.TodoItem.id == todo_id).first()
    if t: t.is_completed = True; t.status = "Tamamlandı"; t.completed_at = datetime.utcnow(); db.commit()
    return {"m": "ok"}

@app.delete("/api/todos/{todo_id}")
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    t = db.query(models.TodoItem).filter(models.TodoItem.id == todo_id).first()
    if t: t.is_completed = True; t.status = "İptal Edildi"; t.completed_at = datetime.utcnow(); db.commit()
    return {"m": "ok"}

@app.post("/api/cases/{case_id}/upload")
def upload_document(case_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    dosya_adi = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    yolu = f"uploads/{dosya_adi}"
    with open(yolu, "wb+") as f: shutil.copyfileobj(file.file, f)
    db.add(models.Document(evrak_adi=file.filename, dosya_yolu=yolu, case_id=case_id))
    db.commit()
    return {"m": "ok"}

@app.post("/api/chat")
def ai_chat(req: ChatRequest): return {"reply": f"Ben Mehmet Alparslan. Sisteminizin yerleşik yapay zekasıyım. Hukuki sorunuzu analiz ettim. Somut olay verilerine göre hareket edilmelidir."}

@app.post("/api/generate-petition")
def generate_petition(req: PetitionRequest, db: Session = Depends(get_db)):
    c = db.query(models.CaseFile).filter(models.CaseFile.dosya_no == req.dosya_no).first()
    text = f"İLGİLİ MAHKEME HAKİMLİĞİNE\n\nDOSYA NO: {req.dosya_no}\nMÜVEKKİL: {c.owner.ad_soyad if c else ''}\nKONU: {req.dilekce_turu}\n\nGereğinin yapılmasını arz ederiz.\n\nAv. Merve Safa Alparslan"
    return {"dilekce_metni": text}

@app.get("/api/search-client")
def search_client(query: str, db: Session = Depends(get_db)):
    cases = db.query(models.CaseFile).join(models.Client).filter((models.Client.tc_kimlik.contains(query)) | (models.CaseFile.dosya_no.contains(query)) | (models.Client.ad_soyad.ilike(f"%{query}%"))).all()
    return [{"id": c.id, "dosya_no": c.dosya_no, "muvekkil": c.owner.ad_soyad, "tur": c.tur.value, "durum": c.durum, "is_closed": c.is_closed} for c in cases]
