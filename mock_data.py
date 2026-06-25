from database import SessionLocal, engine, Base
from models import Client, CaseFile, CaseType, Hearing, TodoItem, Account, CaseStage, Document, OfficeExpense, User, Payment
from datetime import date, timedelta, datetime
import random

def create_mock_data():
    print("Mevcut veritabanı temizleniyor...")
    Base.metadata.drop_all(bind=engine)
    print("Kurumsal tablolar A'dan Z'ye oluşturuluyor...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    admin = User(username="merve", password_hash="merve2026", ad_soyad="Av. Merve Safa Alparslan", role="Kurucu")
    db.add(admin)
    
    isimler = ["Aksiyom Lojistik A.Ş.", "TeknoYapi İnşaat", "Global Pazarlama Ltd.", "Ahmet Yılmaz", "Ayşe Demir", "Mehmet Kaya"]
    turler = list(CaseType)
    durumlar = ["Dilekçe Bekleniyor", "Bilirkişi İncelemesinde", "Tensip Zaptı Hazırlandı", "İstinafta", "Karara Çıktı"]
    
    clients = []
    for i, isim in enumerate(isimler):
        c = Client(tc_kimlik=f"{random.randint(10000000000, 99999999999)}", ad_soyad=isim, telefon=f"0555 {random.randint(100,999)} 12 34", eposta=f"info{i}@ornek.com", kurumsal_mi=(i<3))
        db.add(c)
        clients.append(c)
    db.commit()

    cases = []
    # 20 Adet Aktif, 5 Adet Kapalı Dosya Oluşturuyoruz (0 Hatasını Önlemek İçin)
    for i in range(25):
        c = random.choice(clients)
        ucret = float(random.randint(15000, 100000))
        is_closed = True if i > 19 else False
        case = CaseFile(dosya_no=f"2026/{random.randint(100,999)} {'Esas' if random.choice([True,False]) else 'Takip'}", karsi_taraf=f"Karşı Taraf {i}", tur=random.choice(turler), durum="KAPALI" if is_closed else random.choice(durumlar), anlasilan_ucret=ucret, is_closed=is_closed, client_id=c.id)
        db.add(case)
        cases.append(case)
        if not c.account: db.add(Account(client_id=c.id, toplam_borc=ucret, odenen=0.0))
        else: c.account.toplam_borc += ucret
    db.commit()

    for case in cases:
        db.add(CaseStage(aciklama="Dosya açılışı yapıldı.", case_id=case.id))
        db.add(Document(evrak_adi="Vekaletname_Taranmis.pdf", case_id=case.id))
        if not case.is_closed:
            db.add(Hearing(tarih=date.today() + timedelta(days=random.randint(1, 30)), mahkeme=f"Ankara {random.randint(1,10)}. Asliye Hukuk", saat="10:30", case_id=case.id))

    for c in clients:
        if c.account and c.account.toplam_borc > 0:
            odenen = c.account.toplam_borc * 0.3
            c.account.odenen += odenen
            db.add(Payment(client_id=c.id, miktar=odenen))

    for g in [("Ofis Kirası", "Kira", 15000), ("Elektrik", "Fatura", 1200), ("Kırtasiye", "Kırtasiye", 500)]:
        db.add(OfficeExpense(kalem=g[0], kategori=g[1], tutar=g[2], tarih=date.today()))

    db.add(TodoItem(task="Bilirkişi raporuna itiraz edilecek.", detay="2026/145 Esas nolu dosya acil!"))
    db.add(TodoItem(task="Müvekkil Ahmet Yılmaz aranacak.", detay="Duruşma tarihi bildirilecek."))
    db.commit()
    print("Sistem başarıyla kuruldu! Tüm veriler yüklendi.")

if __name__ == "__main__":
    create_mock_data()
