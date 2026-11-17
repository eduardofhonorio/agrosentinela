"""Cadastro (MySQL) com enriquecimento automático via ViaCEP + geocodificação."""
from datetime import date

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import conexoes
from app.routers.util import registros
from app.services import apis_externas

router = APIRouter(prefix="/api", tags=["Cadastro"])


class Produtor(BaseModel):
    nome: str = Field(min_length=3)
    telefone: str | None = None
    email: str | None = None


class Propriedade(BaseModel):
    produtor_id: int
    nome: str = Field(min_length=3)
    cep: str
    logradouro: str | None = None
    bairro: str | None = None
    cidade: str
    uf: str = Field(min_length=2, max_length=2)
    ibge: str | None = None
    latitude: float
    longitude: float


class Talhao(BaseModel):
    propriedade_id: int
    codigo: str = Field(pattern=r"^[A-Za-z]{3}-\d{2}$")
    nome: str = Field(min_length=3)
    cultura_id: int
    area_ha: float = Field(gt=0)
    data_plantio: date | None = None
    irrigado: bool = False
    latitude: float | None = None
    longitude: float | None = None


@router.get("/cep/{cep}")
def consultar_cep(cep: str):
    """ViaCEP (endereço + IBGE) -> Open-Meteo Geocoding (coordenadas do município)."""
    try:
        end = apis_externas.consultar_cep(cep)
        geo = apis_externas.geocodificar_municipio(end["localidade"], end["uf"])
    except apis_externas.ErroApiExterna as e:
        raise HTTPException(400, str(e)) from e
    return {
        "cep": end["cep"], "logradouro": end.get("logradouro"), "bairro": end.get("bairro"),
        "cidade": end["localidade"], "uf": end["uf"], "ibge": end.get("ibge"),
        "latitude": geo["latitude"], "longitude": geo["longitude"], "elevacao": geo.get("elevacao"),
        "fontes": ["ViaCEP", "Open-Meteo Geocoding"],
    }


@router.get("/cadastro/opcoes")
def opcoes():
    eng = conexoes.mysql()
    return {
        "produtores": registros(pd.read_sql("SELECT id, nome FROM produtores ORDER BY nome", eng)),
        "culturas": registros(pd.read_sql("SELECT * FROM culturas ORDER BY nome", eng)),
        "propriedades": registros(pd.read_sql(
            "SELECT p.id, p.nome, p.cidade, p.uf, p.latitude, p.longitude, pr.nome AS produtor "
            "FROM propriedades p JOIN produtores pr ON pr.id = p.produtor_id ORDER BY p.nome", eng)),
        "talhoes": registros(pd.read_sql(
            "SELECT t.id, t.codigo, t.nome, t.area_ha, t.irrigado, c.nome AS cultura, p.nome AS propriedade, p.cidade "
            "FROM talhoes t JOIN culturas c ON c.id=t.cultura_id JOIN propriedades p ON p.id=t.propriedade_id "
            "ORDER BY t.codigo", eng)),
    }


@router.post("/cadastro/produtores", status_code=201)
def criar_produtor(p: Produtor):
    with conexoes.mysql().begin() as con:
        r = con.execute(text("INSERT INTO produtores (nome, telefone, email) VALUES (:nome,:telefone,:email)"),
                        p.model_dump())
    return {"id": r.lastrowid}


@router.post("/cadastro/propriedades", status_code=201)
def criar_propriedade(p: Propriedade):
    dados = p.model_dump()
    dados["uf"] = dados["uf"].upper()
    with conexoes.mysql().begin() as con:
        r = con.execute(text("""
            INSERT INTO propriedades (produtor_id,nome,cep,logradouro,bairro,cidade,uf,ibge,latitude,longitude)
            VALUES (:produtor_id,:nome,:cep,:logradouro,:bairro,:cidade,:uf,:ibge,:latitude,:longitude)"""), dados)
    return {"id": r.lastrowid}


@router.post("/cadastro/talhoes", status_code=201)
def criar_talhao(t: Talhao):
    dados = t.model_dump()
    dados["codigo"] = dados["codigo"].upper()
    with conexoes.mysql().begin() as con:
        if dados["latitude"] is None or dados["longitude"] is None:
            prop = con.execute(text("SELECT latitude, longitude FROM propriedades WHERE id=:id"),
                               {"id": dados["propriedade_id"]}).first()
            if not prop:
                raise HTTPException(404, "Propriedade não encontrada")
            dados["latitude"], dados["longitude"] = float(prop.latitude), float(prop.longitude)
        try:
            r = con.execute(text("""
                INSERT INTO talhoes (propriedade_id,codigo,nome,cultura_id,area_ha,data_plantio,irrigado,latitude,longitude)
                VALUES (:propriedade_id,:codigo,:nome,:cultura_id,:area_ha,:data_plantio,:irrigado,:latitude,:longitude)"""),
                dados)
        except IntegrityError as e:
            raise HTTPException(409, f"Código de talhão {dados['codigo']} já existe") from e
    return {"id": r.lastrowid, "mensagem": "Talhão cadastrado. Execute a integração para gerar os indicadores."}
