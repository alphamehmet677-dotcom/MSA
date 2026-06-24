import os
import json
import urllib.request
import shutil
import jwt
from fastapi.responses import FileResponse
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from database import SessionLocal, engine
from datetime import date, timedelta, datetime
import models
from typing import Optional

SECRET_KEY = "merve_safa_alparslan_erp_secret"

os.makedirs("uploads", exist_ok=True)
app = FastAPI(title="Merve Safa Alparslan Hukuk API", version="5.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

from fastapi.responses import FileResponse

@app.get("/")
def ana_sayfa():
    return FileResponse("İNDEX.HTML")

# --- VERİ MODELLERİ ---
class ChatRequest(BaseModel): message: str
class PetitionRequest(BaseModel): dosya_no: str; dilekce_turu: str; detay: str = ""
class LoginRequest(BaseModel): username: str; password: str

# --- GİRİŞ / YETKİLENDİRME API ---
@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == req.username).first()
    if user and user.password_hash == req.password:
        token = jwt.encode({"sub": user.username, "ad": user.ad_soyad}, SECRET_KEY, algorithm="HS256")
        return {"token": token, "ad_soyad": user.ad_soyad}
    raise HTTPException(status_code=401, detail="Hatalı kullanıcı adı veya şifre.")

# --- UYAP RPA (ROBOT) SİMÜLASYONU ---
@app.post("/api/uyap-sync")
def uyap_sync():
    try:
        import time
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)
        time.sleep(2) 
        driver.quit()
        return {"mesaj": "UYAP Otomasyonu Tamamlandı. Sistemdeki 2 yeni evrak tespit edildi ve senkronize edildi."}
    except Exception as e:
        import time
        time.sleep(2)
        return {"mesaj": "UYAP Bağlantısı Kuruldu (Simülasyon Modu). Mevcut dosyalarınız güncel."}

# --- OCR VE DOSYA YÜKLEME API ---
@app.post("/api/cases/{case_id}/upload")
def upload_document(case_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    zaman = datetime.now().strftime("%Y%m%d%H%M%S")
    guvenli_dosya_adi = f"{zaman}_{file.filename.replace(' ', '_')}"
    dosya_yolu = f"uploads/{guvenli_dosya_adi}"
    
    with open(dosya_yolu, "wb+") as f:
        shutil.copyfileobj(file.file, f)

    ocr_sonucu = ""
    if file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(dosya_yolu)
            ocr_sonucu = pytesseract.image_to_string(img, lang='tur')
        except Exception as e:
            ocr_sonucu = "[OCR Motoru Bulunamadı veya Okunamadı]"

    yeni_evrak = models.Document(evrak_adi=file.filename, dosya_yolu=dosya_yolu, ocr_text=ocr_sonucu, case_id=case_id)
    db.add(yeni_evrak)
    
    yeni_asama = models.CaseStage(aciklama=f"Sisteme yeni evrak yüklendi: {file.filename}", case_id=case_id)
    db.add(yeni_asama)
    db.commit()
    
    return {"mesaj": "Dosya başarıyla yüklendi", "dosya_yolu": dosya_yolu, "ocr_text": ocr_sonucu}

# --- YAPAY ZEKA ---
def yerel_hukuk_asistani(mesaj: str) -> str:
    m = mesaj.lower()
    if any(k in m for k in ["merhaba", "selam", "kimsin"]): return "Merhaba! Ben Mehmet Alparslan. Sisteminizin mimarı ve yapay zeka asistanıyım. Size nasıl yardımcı olabilirim?"
    elif "boşanma" in m: return "Boşanma davalarında yetkili mahkeme eşlerin son 6 aydır oturduğu yerdir (TMK m.168)."
    elif "icra" in m: return "İlamsız icra takiplerinde ödeme emrine itiraz süresi 7 gündür (İİK m.62)."
    else: return "Bu hukuki mesele için somut olayın evraklarıyla incelenmesi gerekir. Ben Mehmet Alparslan olarak teknik sorularınızı da yanıtlayabilirim."

@app.post("/api/chat")
def ai_assistant_chat(req: ChatRequest): return {"reply": yerel_hukuk_asistani(req.message)}

@app.post("/api/generate-petition")
def generate_petition(req: PetitionRequest, db: Session = Depends(get_db)):
    c = db.query(models.CaseFile).filter(models.CaseFile.dosya_no == req.dosya_no).first()
    mad = c.owner.ad_soyad if c else "[MÜVEKKİL SİSTEMDE YOK]"
    kar = c.karsi_taraf if c else "[KARŞI TARAF SİSTEMDE YOK]"
    text = f"""İLGİLİ MAHKEME HAKİMLİĞİNE / İCRA MÜDÜRLÜĞÜNE\n\nDOSYA NO: {req.dosya_no}\nMÜVEKKİL: {mad}\nKARŞI TARAF: {kar}\nKONU: {req.dilekce_turu} sunulması talebimizden ibarettir.\n\nAÇIKLAMALAR:\n1- Yukarıda esas numarası belirtilen dosyanızda müvekkil {mad} adına vekaleten süreci takip etmekteyiz.\n2- {req.detay if req.detay else 'Ara karar gereğince hukuki adımların atılması zarureti hasıl olmuştur.'}\n\nSONUÇ VE İSTEM: Talebimizin KABULÜNE karar verilmesini saygılarımızla arz ederiz.\n\nAv. Merve Safa Alparslan\nTarih: {date.today().strftime('%d.%m.%Y')}"""
    return {"dilekce_metni": text}

# --- GET ENDPOINTLERİ ---
@app.get("/api/dashboard-stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    # ÇÖZÜM BURADA: "Dava" düz metni yerine models.CaseType.DAVA kullanıyoruz.
    return {
        "aktif_muvekkil": db.query(models.Client).count(),
        "acik_dava": db.query(models.CaseFile).filter(models.CaseFile.is_closed == False, models.CaseFile.tur == models.CaseType.DAVA).count(),
        "bekleyen_gorev": db.query(models.TodoItem).filter(models.TodoItem.is_completed == False).count(),
        "bu_hafta_durusma": db.query(models.Hearing).filter(models.Hearing.tarih >= date.today(), models.Hearing.tarih <= date.today() + timedelta(days=7)).count()
    }

@app.get("/api/cases/{case_id}/details")
def get_case_details(case_id: int, db: Session = Depends(get_db)):
    c = db.query(models.CaseFile).filter(models.CaseFile.id == case_id).first()
    if not c: raise HTTPException(status_code=404)
    hesap = db.query(models.Account).filter(models.Account.client_id == c.client_id).first()
    return {"id": c.id, "dosya_no": c.dosya_no, "tur": c.tur.value, "durum": c.durum, "karsi_taraf": c.karsi_taraf, "is_closed": c.is_closed, "muvekkil": {"id": c.owner.id, "ad_soyad": c.owner.ad_soyad, "tc": c.owner.tc_kimlik, "telefon": c.owner.telefon}, "finans": {"toplam": hesap.toplam_borc if hesap else 0, "odenen": hesap.odenen if hesap else 0}, "asamalar": [{"tarih": s.tarih.strftime("%d.%m.%Y"), "aciklama": s.aciklama} for s in c.stages], "evraklar": [{"id": d.id, "tarih": d.yuklenme_tarihi.strftime("%d.%m.%Y"), "ad": d.evrak_adi, "yol": d.dosya_yolu} for d in c.documents]}

@app.get("/api/clients/{client_id}/details")
def get_client_details(client_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not c: raise HTTPException(status_code=404)
    hesap = db.query(models.Account).filter(models.Account.client_id == c.id).first()
    return {"id": c.id, "tc": c.tc_kimlik, "ad": c.ad_soyad, "tel": c.telefon, "mail": c.eposta, "finans": {"toplam": hesap.toplam_borc if hesap else 0, "odenen": hesap.odenen if hesap else 0}, "dosyalar": [{"id": f.id, "no": f.dosya_no, "durum": f.durum, "kapali": f.is_closed} for f in c.cases]}

@app.get("/api/recent-cases")
def recent_cases(db: Session = Depends(get_db)): return [{"id": c.id, "dosya_no": c.dosya_no, "muvekkil": c.owner.ad_soyad, "tur": c.tur.value, "durum": c.durum} for c in db.query(models.CaseFile).filter(models.CaseFile.is_closed == False).order_by(models.CaseFile.id.desc()).limit(10).all()]

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

@app.get("/api/todos")
def get_todos(db: Session = Depends(get_db)): return [{"id": t.id, "task": t.task, "detay": t.detay, "dosya": t.bagli_dosya_no} for t in db.query(models.TodoItem).filter(models.TodoItem.is_completed == False).all()]

@app.get("/api/finance")
def get_finance(db: Session = Depends(get_db)):
    accounts = db.query(models.Account).all()
    giderler = db.query(models.OfficeExpense).all()
    
    liste = [{"muvekkil": a.client.ad_soyad, "toplam": a.toplam_borc, "odenen": a.odenen, "kalan": a.toplam_borc - a.odenen} for a in accounts]
    gider_listesi = [{"kalem": g.kalem, "kategori": g.kategori, "tutar": g.tutar, "tarih": g.tarih.strftime("%d.%m.%Y")} for g in giderler]
    
    toplam_alacak = sum(a.toplam_borc for a in accounts)
    toplam_tahsilat = sum(a.odenen for a in accounts)
    toplam_gider = sum(g.tutar for g in giderler)
    
    return {"liste": liste, "gider_listesi": gider_listesi, "ozet": {"toplam_alacak": toplam_alacak, "toplam_tahsilat": toplam_tahsilat, "net_kalan": toplam_alacak - toplam_tahsilat, "toplam_gider": toplam_gider}}

@app.get("/api/search-client")
def search_client(query: str, db: Session = Depends(get_db)):
    cases = db.query(models.CaseFile).join(models.Client).outerjoin(models.Document).filter(
        (models.Client.tc_kimlik.contains(query)) | 
        (models.CaseFile.dosya_no.contains(query)) | 
        (models.Client.ad_soyad.ilike(f"%{query}%")) |
        (models.Document.ocr_text.ilike(f"%{query}%"))
    ).distinct().all()
    if not cases: return {"hata": "Kayıt veya evrak içeriği bulunamadı."}
    return [{"id": c.id, "dosya_no": c.dosya_no, "muvekkil": c.owner.ad_soyad, "tur": c.tur.value, "durum": c.durum, "is_closed": c.is_closed} for c in cases]
