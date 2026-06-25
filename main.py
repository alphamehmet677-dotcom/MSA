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
from sqlalchemy import func
from pydantic import BaseModel
from database import SessionLocal, engine
from datetime import date, timedelta, datetime
import models
import mock_data # YENİ: Otomatik onarım için eklendi

SECRET_KEY = "merve_safa_alparslan_erp_secret"

# ---------------------------------------------------------
# YENİ: AKILLI VERİTABANI ONARIM SİSTEMİ (SELF-HEALING)
# ---------------------------------------------------------
models.Base.metadata.create_all(bind=engine)

try:
    # Veritabanında yeni eklediğimiz "password" sütunu var mı diye test et
    db_check = SessionLocal()
    db_check.query(models.Client.password).first()
    db_check.close()
except Exception as e:
    # Eğer hata verirse (sütun yoksa), eski tabloları silip yeni yapıyla mock_data'yı çalıştır
    print("Sistem Uyarısı: Eski veritabanı şeması tespit edildi. Tablolar onarılıyor...")
    mock_data.create_mock_data()

# Yönetici hesabının varlığını garantiye al
db_init = SessionLocal()
if not db_init.query(models.User).filter(models.User.username == "merve").first():
    db_init.add(models.User(username="merve", password_hash="merve2026", ad_soyad="Av. Merve Safa Alparslan", role="Kurucu"))
    db_init.commit()
db_init.close()
# ---------------------------------------------------------

os.makedirs("uploads", exist_ok=True)
app = FastAPI(title="Merve Safa Alparslan Hukuk ERP API", version="7.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def ana_sayfa():
    return FileResponse("İNDEX.HTML")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- VERİ ŞEMALARI ---
class ChatRequest(BaseModel): message: str
class PetitionRequest(BaseModel): dosya_no: str; dilekce_turu: str; detay: str = ""
class LoginRequest(BaseModel): username: str; password: str
class TodoCreate(BaseModel): task: str; detay: str = ""
class ClientCaseCreate(BaseModel): tc_kimlik: str; ad_soyad: str; telefon: str = ""; dosya_no: str; karsi_taraf: str; tur: str
class CaseUpdate(BaseModel): durum: str; karsi_taraf: str
class ExpenseCreate(BaseModel): kalem: str; kategori: str; tutar: float

# --- GİRİŞ / ÇİFT ROL YETKİLENDİRME ---
@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == req.username).first()
    if user and user.password_hash == req.password:
        return {"token": jwt.encode({"sub": user.username, "role": "Avukat", "ad": user.ad_soyad}, SECRET_KEY, algorithm="HS256"), "role": "Avukat", "ad_soyad": user.ad_soyad}
    
    client = db.query(models.Client).filter(models.Client.tc_kimlik == req.username).first()
    if client and client.password == req.password:
        return {"token": jwt.encode({"sub": client.tc_kimlik, "role": "Müvekkil", "ad": client.ad_soyad, "id": client.id}, SECRET_KEY, algorithm="HS256"), "role": "Müvekkil", "ad_soyad": client.ad_soyad, "client_id": client.id}
        
    raise HTTPException(status_code=401, detail="Hatalı Kimlik.")

# --- MÜVEKKİL PORTALI VERİ ÇEKME ---
@app.get("/api/client-portal/{client_id}/dashboard")
def get_client_portal_data(client_id: int, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client: raise HTTPException(status_code=404)
    hesap = client.account
    return {
        "profil": {"ad": client.ad_soyad, "tc": client.tc_kimlik, "tel": client.telefon},
        "finans": {"toplam": hesap.toplam_borc if hesap else 0, "odenen": hesap.odenen if hesap else 0, "kalan": (hesap.toplam_borc - hesap.odenen) if hesap else 0},
        "dosyalar": [{"id": c.id, "dosya_no": c.dosya_no, "tur": c.tur.value, "durum": c.durum, "karsi_taraf": c.karsi_taraf, "asamalar": [{"tarih": s.tarih.strftime("%d.%m.%Y"), "aciklama": s.aciklama} for s in c.stages], "evraklar": [{"ad": d.evrak_adi, "yol": d.dosya_yolu} for d in c.documents]} for c in client.cases]
    }

# --- C.R.U.D. (DÜZENLEME VE SİLME) ENDPOINTLERİ ---
@app.delete("/api/cases/{case_id}")
def delete_case(case_id: int, db: Session = Depends(get_db)):
    case = db.query(models.CaseFile).filter(models.CaseFile.id == case_id).first()
    if case: db.delete(case); db.commit()
    return {"mesaj": "Dosya silindi."}

@app.put("/api/cases/{case_id}")
def update_case(case_id: int, req: CaseUpdate, db: Session = Depends(get_db)):
    case = db.query(models.CaseFile).filter(models.CaseFile.id == case_id).first()
    if case: case.durum = req.durum; case.karsi_taraf = req.karsi_taraf; db.commit()
    return {"mesaj": "Güncellendi."}

@app.post("/api/expenses")
def create_expense(req: ExpenseCreate, db: Session = Depends(get_db)):
    db.add(models.OfficeExpense(kalem=req.kalem, kategori=req.kategori, tutar=req.tutar))
    db.commit()
    return {"mesaj": "Gider Eklendi"}

@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    exp = db.query(models.OfficeExpense).filter(models.OfficeExpense.id == expense_id).first()
    if exp: db.delete(exp); db.commit()
    return {"mesaj": "Gider Silindi"}

# --- YENİ KAYIT ---
@app.post("/api/add-client-case")
def add_client_case(data: ClientCaseCreate, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(models.Client.tc_kimlik == data.tc_kimlik).first()
    if not client:
        client = models.Client(tc_kimlik=data.tc_kimlik, ad_soyad=data.ad_soyad, telefon=data.telefon)
        db.add(client); db.commit(); db.refresh(client)
    try: case_type = models.CaseType(data.tur)
    except: case_type = models.CaseType.DAVA
    yeni_dosya = models.CaseFile(dosya_no=data.dosya_no, karsi_taraf=data.karsi_taraf, tur=case_type, durum="Yeni Açıldı", client_id=client.id)
    db.add(yeni_dosya)
    if not client.account: db.add(models.Account(client_id=client.id, toplam_borc=0.0, odenen=0.0))
    db.add(models.CaseStage(aciklama="Dosya sisteme kaydedildi.", case_id=yeni_dosya.id))
    db.commit()
    return {"mesaj": "Başarılı"}

# --- AJANDA (GÖREV) YÖNETİMİ ---
@app.post("/api/todos")
def create_todo(todo: TodoCreate, db: Session = Depends(get_db)):
    db.add(models.TodoItem(task=todo.task, detay=todo.detay)); db.commit()
    return {"mesaj": "Görev Eklendi"}

@app.get("/api/todos")
def get_todos(db: Session = Depends(get_db)):
    return [{"id": t.id, "task": t.task, "detay": t.detay, "dosya": t.bagli_dosya_no} for t in db.query(models.TodoItem).filter(models.TodoItem.is_completed == False).all()]

@app.get("/api/todos/archive")
def get_todo_archive(db: Session = Depends(get_db)): 
    return [{"task": t.task, "detay": t.detay, "status": t.status, "eklenme": t.created_at.strftime("%d.%m.%Y"), "bitis": t.completed_at.strftime("%d.%m.%Y") if t.completed_at else "-"} for t in db.query(models.TodoItem).filter(models.TodoItem.is_completed == True).all()]

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

# --- DOSYA VE OCR YÜKLEME ---
@app.post("/api/cases/{case_id}/upload")
def upload_document(case_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    dosya_adi = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename.replace(' ', '_')}"
    yolu = f"uploads/{dosya_adi}"
    with open(yolu, "wb+") as f: shutil.copyfileobj(file.file, f)
    
    ocr_sonucu = ""
    if file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        try:
            import pytesseract
            from PIL import Image
            ocr_sonucu = pytesseract.image_to_string(Image.open(yolu), lang='tur')
        except: pass

    db.add(models.Document(evrak_adi=file.filename, dosya_yolu=yolu, ocr_text=ocr_sonucu, case_id=case_id))
    db.add(models.CaseStage(aciklama=f"Sisteme evrak yüklendi: {file.filename}", case_id=case_id))
    db.commit()
    return {"m": "ok"}

# --- YAPAY ZEKA VE DİLEKÇE ---
@app.post("/api/chat")
def ai_chat(req: ChatRequest): return {"reply": "Ben Mehmet Alparslan. Sisteminizin yerleşik yapay zekasıyım. Hukuki sorunuzu analiz ettim. Somut olay verilerine göre hareket edilmelidir."}

@app.post("/api/generate-petition")
def generate_petition(req: PetitionRequest, db: Session = Depends(get_db)):
    c = db.query(models.CaseFile).filter(models.CaseFile.dosya_no == req.dosya_no).first()
    mad = c.owner.ad_soyad if c else "[MÜVEKKİL SİSTEMDE YOK]"
    kar = c.karsi_taraf if c else "[KARŞI TARAF SİSTEMDE YOK]"
    text = f"İLGİLİ MAHKEME HAKİMLİĞİNE\n\nDOSYA NO: {req.dosya_no}\nMÜVEKKİL: {mad}\nKARŞI TARAF: {kar}\nKONU: {req.dilekce_turu} hk.\n\nAÇIKLAMALAR:\n1- Dosyada müvekkil {mad} adına süreci takip etmekteyiz.\n2- {req.detay}\n\nSONUÇ VE İSTEM: Talebimizin KABULÜNE karar verilmesini arz ederiz.\n\nAv. Merve Safa Alparslan\nTarih: {date.today().strftime('%d.%m.%Y')}"
    return {"dilekce_metni": text}

# --- GET ENDPOINTLERİ ---
@app.get("/api/dashboard-stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    return {
        "aktif_muvekkil": db.query(models.Client).count(),
        "acik_dava": db.query(models.CaseFile).filter(models.CaseFile.is_closed == False, models.CaseFile.tur == models.CaseType.DAVA).count(),
        "bekleyen_gorev": db.query(models.TodoItem).filter(models.TodoItem.is_completed == False).count(),
        "bu_hafta_durusma": db.query(models.Hearing).filter(models.Hearing.tarih >= date.today(), models.Hearing.tarih <= date.today() + timedelta(days=7)).count()
    }

@app.get("/api/recent-cases")
def recent_cases(db: Session = Depends(get_db)): return [{"id": c.id, "dosya_no": c.dosya_no, "muvekkil": c.owner.ad_soyad, "karsi_taraf": c.karsi_taraf, "tur": c.tur.value, "durum": c.durum} for c in db.query(models.CaseFile).filter(models.CaseFile.is_closed == False).order_by(models.CaseFile.id.desc()).limit(10).all()]

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

@app.get("/api/cases/{case_id}/details")
def get_case_details(case_id: int, db: Session = Depends(get_db)):
    c = db.query(models.CaseFile).filter(models.CaseFile.id == case_id).first()
    hesap = db.query(models.Account).filter(models.Account.client_id == c.client_id).first()
    return {"id": c.id, "dosya_no": c.dosya_no, "tur": c.tur.value, "durum": c.durum, "karsi_taraf": c.karsi_taraf, "is_closed": c.is_closed, "muvekkil": {"id": c.owner.id, "ad_soyad": c.owner.ad_soyad, "tc": c.owner.tc_kimlik, "telefon": c.owner.telefon}, "finans": {"toplam": hesap.toplam_borc if hesap else 0, "odenen": hesap.odenen if hesap else 0}, "asamalar": [{"tarih": s.tarih.strftime("%d.%m.%Y"), "aciklama": s.aciklama} for s in c.stages], "evraklar": [{"id": d.id, "tarih": d.yuklenme_tarihi.strftime("%d.%m.%Y"), "ad": d.evrak_adi, "yol": d.dosya_yolu} for d in c.documents]}

@app.get("/api/clients/{client_id}/details")
def get_client_details(client_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Client).filter(models.Client.id == client_id).first()
    hesap = db.query(models.Account).filter(models.Account.client_id == c.id).first()
    return {"id": c.id, "tc": c.tc_kimlik, "ad": c.ad_soyad, "tel": c.telefon, "mail": c.eposta, "finans": {"toplam": hesap.toplam_borc if hesap else 0, "odenen": hesap.odenen if hesap else 0}, "dosyalar": [{"id": f.id, "no": f.dosya_no, "durum": f.durum, "kapali": f.is_closed} for f in c.cases]}

@app.get("/api/search-client")
def search_client(query: str, db: Session = Depends(get_db)):
    cases = db.query(models.CaseFile).join(models.Client).outerjoin(models.Document).filter((models.Client.tc_kimlik.contains(query)) | (models.CaseFile.dosya_no.contains(query)) | (models.Client.ad_soyad.ilike(f"%{query}%")) | (models.Document.ocr_text.ilike(f"%{query}%"))).distinct().all()
    return [{"id": c.id, "dosya_no": c.dosya_no, "muvekkil": c.owner.ad_soyad, "tur": c.tur.value, "durum": c.durum, "is_closed": c.is_closed} for c in cases]
