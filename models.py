from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum, Boolean, DateTime, Float, Text
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime, date

class CaseType(enum.Enum):
    DAVA = "Dava"
    ICRA = "İcra"
    DANISMANLIK = "Danışmanlık"
    CEZA = "Ceza Hukuku"
    AILE = "Aile Hukuku"
    IS = "İş Hukuku"
    IDARE = "İdare ve Vergi"
    ARABULUCULUK = "Arabuluculuk"
    TUKETICI = "Tüketici Hukuku"
    TICARET = "Ticaret Hukuku"
    MIRAS = "Miras Hukuku"
    GAYRIMENKUL = "Gayrimenkul Hukuku"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="Avukat")
    ad_soyad = Column(String)

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    tc_kimlik = Column(String, unique=True, index=True)
    ad_soyad = Column(String, index=True)
    password = Column(String, default="123456") 
    telefon = Column(String, nullable=True)
    eposta = Column(String, nullable=True)
    adres = Column(Text, nullable=True)
    kurumsal_mi = Column(Boolean, default=False)
    kayit_tarihi = Column(DateTime, default=datetime.utcnow)
    notlar = Column(Text, nullable=True)

    cases = relationship("CaseFile", back_populates="owner", cascade="all, delete-orphan")
    account = relationship("Account", back_populates="client", uselist=False, cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="client", cascade="all, delete-orphan")

class CaseFile(Base):
    __tablename__ = "case_files"
    id = Column(Integer, primary_key=True, index=True)
    dosya_no = Column(String, index=True) 
    karsi_taraf = Column(String)
    tur = Column(Enum(CaseType))
    durum = Column(String) 
    anlasilan_ucret = Column(Float, default=0.0)
    is_closed = Column(Boolean, default=False)
    kapanis_tarihi = Column(DateTime, nullable=True)
    acilis_tarihi = Column(DateTime, default=datetime.utcnow)
    client_id = Column(Integer, ForeignKey("clients.id"))
    
    owner = relationship("Client", back_populates="cases")
    hearings = relationship("Hearing", back_populates="case_file", cascade="all, delete-orphan")
    stages = relationship("CaseStage", back_populates="case_file", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="case_file", cascade="all, delete-orphan")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    miktar = Column(Float)
    tarih = Column(DateTime, default=datetime.utcnow)
    odeme_yontemi = Column(String, default="Banka") # YENİ: Kasa veya Banka
    makbuz_no = Column(String, nullable=True) # YENİ: Makbuz numarası
    aciklama = Column(String, nullable=True) # YENİ: Tahsilat açıklaması
    client_id = Column(Integer, ForeignKey("clients.id"))
    client = relationship("Client", back_populates="payments")

class CaseStage(Base):
    __tablename__ = "case_stages"
    id = Column(Integer, primary_key=True, index=True)
    aciklama = Column(String)
    tarih = Column(DateTime, default=datetime.utcnow)
    case_id = Column(Integer, ForeignKey("case_files.id"))
    case_file = relationship("CaseFile", back_populates="stages")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    evrak_adi = Column(String)
    yuklenme_tarihi = Column(DateTime, default=datetime.utcnow)
    dosya_yolu = Column(String, nullable=True)
    ocr_text = Column(Text, nullable=True) 
    case_id = Column(Integer, ForeignKey("case_files.id"))
    case_file = relationship("CaseFile", back_populates="documents")

class TodoItem(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True, index=True)
    task = Column(String, index=True)
    detay = Column(Text, nullable=True)
    is_completed = Column(Boolean, default=False)
    status = Column(String, default="Aktif") 
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    bagli_dosya_no = Column(String, nullable=True)

class Hearing(Base):
    __tablename__ = "hearings"
    id = Column(Integer, primary_key=True, index=True)
    tarih = Column(Date)
    saat = Column(String, nullable=True)
    mahkeme = Column(String) 
    case_id = Column(Integer, ForeignKey("case_files.id"))
    case_file = relationship("CaseFile", back_populates="hearings")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), unique=True)
    toplam_borc = Column(Float, default=0.0)
    odenen = Column(Float, default=0.0)
    client = relationship("Client", back_populates="account")

class OfficeExpense(Base):
    __tablename__ = "office_expenses"
    id = Column(Integer, primary_key=True, index=True)
    kalem = Column(String)
    kategori = Column(String) 
    tutar = Column(Float)
    kdv_orani = Column(Integer, default=20) # YENİ: KDV oranı
    odeme_yontemi = Column(String, default="Banka") # YENİ: Kasa veya Banka
    fatura_no = Column(String, nullable=True) # YENİ: Fatura numarası
    tarih = Column(Date, default=date.today)
