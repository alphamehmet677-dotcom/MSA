from database import SessionLocal, engine, Base
from models import Client, CaseFile, CaseType, Hearing, TodoItem, Account, CaseStage, Document, OfficeExpense, User
from datetime import date, timedelta, datetime
import random

def create_mock_data():
    print("Mevcut veritabanı temizleniyor...")
    Base.metadata.drop_all(bind=engine)
    print("Yeni profesyonel tablolar oluşturuluyor...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    print("Yönetici Hesabı Oluşturuluyor...")
    admin = User(username="merve", password_hash="merve2026", ad_soyad="Av. Merve Safa Alparslan", role="Kurucu")
    admin2 = User(username="mehmet", password_hash="123456", ad_soyad="Müh. Mehmet Alparslan", role="Sistem Mimarı")
    db.add_all([admin, admin2])
    
    print("Test Verileri (20+ Kayıt) Otomatik Ekleniyor...")
    isimler = ["Aksiyom Lojistik A.Ş.", "TeknoYapi İnşaat", "Global Pazarlama Ltd.", "Ahmet Yılmaz", "Ayşe Demir", "Mehmet Kaya", "Fatma Çelik", "Ali Aslan", "Zeynep Şahin", "Caner Yıldız", "Burak Öz", "Elif Can", "Serkan Taş", "Deniz Bulut", "Hasan Korkmaz"]
    turler = list(CaseType)
    durumlar = ["Dilekçe Bekleniyor", "Bilirkişi İncelemesinde", "Tensip Zaptı Hazırlandı", "İstinafta", "Haciz Aşamasında", "Karara Çıktı"]
    
    clients = []
    for i, isim in enumerate(isimler):
        tc_vergi = f"{random.randint(10000000000, 99999999999)}"
        c = Client(tc_kimlik=tc_vergi, ad_soyad=isim, telefon=f"0555 {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}", eposta=f"info{i}@ornek.com", kurumsal_mi=(i<3))
        db.add(c)
        clients.append(c)
    db.commit()

    cases = []
    for i in range(25):
        c = random.choice(clients)
        case = CaseFile(dosya_no=f"2026/{random.randint(100,999)} {'Esas' if random.choice([True,False]) else 'Takip'}", karsi_taraf=f"Karşı Taraf {i}", tur=random.choice(turler), durum=random.choice(durumlar), client_id=c.id, is_closed=(i%5==0), kapanis_tarihi=datetime.utcnow() if (i%5==0) else None)
        db.add(case)
        cases.append(case)
    db.commit()

    for case in cases:
        db.add(CaseStage(aciklama="Dava açılış dilekçesi sunuldu.", case_id=case.id))
        db.add(Document(evrak_adi="Vekaletname.pdf", case_id=case.id))
        if not case.is_closed:
            db.add(Hearing(tarih=date.today() + timedelta(days=random.randint(1, 30)), mahkeme=f"Ankara {random.randint(1,10)}. Asliye Hukuk", saat="10:30", case_id=case.id))

    for c in clients:
        borc = random.randint(10000, 200000)
        db.add(Account(client_id=c.id, toplam_borc=borc, odenen=random.randint(0, borc)))
    
    giderler = [("Ofis Kirası", "Kira", 15000), ("Elektrik Faturası", "Fatura", 1200), ("Kırtasiye A4", "Kırtasiye", 500), ("Adliye Taksi", "Ulaşım", 250)]
    for g in giderler:
        db.add(OfficeExpense(kalem=g[0], kategori=g[1], tutar=g[2], tarih=date.today() - timedelta(days=random.randint(1,10))))

    db.add(TodoItem(task="Aksiyom Lojistik faturası kesilecek.", detay="KDV dahil kesilecek."))
    db.add(TodoItem(task="Bilirkişi raporuna itiraz dilekçesi yazılacak.", bagli_dosya_no="2026/145 Esas"))
    db.add(TodoItem(task="Müvekkil Ahmet Yılmaz aranacak.", detay="Dosya durumu hakkında bilgi verilecek."))
    db.commit()
    print("Sistem başarıyla kuruldu! Yönetici (merve / merve2026) ile giriş yapabilirsiniz.")

if __name__ == "__main__":
    create_mock_data()
