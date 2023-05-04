from sqlalchemy import create_engine
from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

db_path = "./budget.db"
engine = create_engine("sqlite:///budget.db")
Base = declarative_base()


class Transactions(Base):
    __tablename__ = "Transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Date = Column(String)
    Transaction = Column(String)
    Name = Column(String)
    Memo = Column(String)
    Amount = Column(Float)
    VendorUUID = Column(String)
    Has_Child = Column("Has Child", String)
    Hash = Column(String, unique=True)


class ChildTransactions(Base):
    __tablename__ = "Child Transactions"

    id = Column(Integer, primary_key=True)
    Parent_id = Column(Integer, ForeignKey("Transactions.id"))
    Date = Column(String)
    Transaction = Column(String)
    Name = Column(String)
    Memo = Column(String)
    Amount = Column(Float)
    VendorUUID = Column(String)
    Tag = Column(String)
    Initialized = Column(String)
    Description = Column(String)


class BudgetTemplates(Base):
    __tablename__ = "Budget Templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Budget_Name = Column("Budget Name", String)
    Buckets = Column(String, unique=True)
    Percent = Column(Float)


class BankTemplates(Base):
    __tablename__ = "Bank Templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Bank_Name = Column("Bank Name", String)
    Row_Number = Column("Row Number", Integer)
    Column_Name = Column("Column Name", String)
    Match_To = Column("Match To", String)


class Vendors(Base):
    __tablename__ = "Vendors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Vendor = Column(String, unique=True)
    Pattern = Column(String)
    Tag = Column(String)
    UUID = Column(String)
    Initialized = Column(String)


class ExpenseImports(Base):
    __tablename__ = "Expense Imports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Filename = Column(String, unique=True)


def init_db():
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    return session


if __name__ == "__main__":
    session = init_db()