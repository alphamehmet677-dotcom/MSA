from database import engine, Base
import models

print("Kurumsal Veritabanı bağlantısı kuruluyor ve güvenlik tabloları oluşturuluyor...")
Base.metadata.create_all(bind=engine)
print("İşlem başarılı! Sistem yayınlanmaya hazır.")
