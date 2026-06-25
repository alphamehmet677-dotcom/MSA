from database import SessionLocal, engine, Base
from models import Client, CaseFile, CaseType, Hearing, TodoItem, Account, CaseStage, Document, OfficeExpense, User, Payment
from datetime import date, timedelta, datetime
import random

def create_mock_data():
    print("Mevcut veritabanı temizleniyor...")
    Base.metadata.drop_all(bind=engine)
    print("Yeni A'dan Z'ye profesyonel tablolar oluşturuluyor...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    print("Yönetici Hesabı Oluşturuluyor...")
    admin = User(username="merve", password_hash="merve2026", ad_soyad="Av. Merve Safa Alparslan", role="Kurucu")
    admin2 = User(username="mehmet", password_hash="123456", ad_soyad="Müh. Mehmet Alparslan", role="Sistem Mimarı")
    db.add_all([admin, admin2])
    
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
    for i in range(15):
        c = random.choice(clients)
        ucret = float(random.randint(20000, 150000))
        case = CaseFile(dosya_no=f"2026/{random.randint(100,999)} Esas", karsi_taraf=f"Karşı Taraf {i}", tur=random.choice(turler), durum=random.choice(durumlar), anlasilan_ucret=ucret, client_id=c.id)
        db.add(case)
        cases.append(case)
        
        # Cari hesap güncelleniyor
        if not c.account: db.add(Account(client_id=c.id, toplam_borc=ucret, odenen=0.0))
        else: c.account.toplam_borc += ucret
            
    db.commit()

    # Tahsilatlar ve Giderler (Aylık Finans İçin)
    for c in clients:
        if c.account and c.account.toplam_borc > 0:
            odenen = c.account.toplam_borc * 0.4
            c.account.odenen += odenen
            db.add(Payment(client_id=c.id, miktar=odenen)) # Bu aya gelir yansıt

    for g in [("Ofis Kirası", "Kira", 15000), ("Elektrik", "Fatura", 1200), ("Kırtasiye", "Kırtasiye", 500)]:
        db.add(OfficeExpense(kalem=g[0], kategori=g[1], tutar=g[2], tarih=date.today()))

    db.add(TodoItem(task="Bilirkişi raporuna itiraz edilecek.", detay="2026/145 Esas"))
    db.commit()
    print("Sistem başarıyla kuruldu! Giriş yapabilirsiniz.")

if __name__ == "__main__":
    create_mock_data()
