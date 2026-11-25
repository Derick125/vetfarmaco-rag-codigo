"""Testes de etl/load.py — idempotência por texto_hash (docs/DATABASE.md §2).

Usa uma conexão Postgres falsa (sem rede, sem servidor real) para testar
o controle de idempotência e a criação/reuso de `documento`; não valida
SQL contra um Postgres de verdade — isso depende de `DATABASE_URL`
apontar para uma instância real (ver backend/scripts/verificar_schema.py).
"""

import contextlib
import re

from etl.load import RegistroCarga, calcular_indice_versao, carregar


class _CursorFalso:
    """Despacha `fetchone`/`fetchall` conforme o último `execute` (por
    substring do SQL) — mais legível que uma fila posicional de resultados.
    """

    def __init__(self, *, documento_encontrado=None, novo_documento_id=None, hashes_existentes=()):
        self.comandos: list[tuple[str, tuple]] = []
        self._documento_encontrado = documento_encontrado
        self._novo_documento_id = novo_documento_id
        self._hashes_existentes = [(h,) for h in hashes_existentes]
        self._ultimo_comando = ""

    def execute(self, sql, params=None):
        self._ultimo_comando = " ".join(sql.split())
        self.comandos.append((self._ultimo_comando, params))

    def fetchone(self):
        if "select id from documento" in self._ultimo_comando:
            return self._documento_encontrado
        if "insert into documento" in self._ultimo_comando:
            return (self._novo_documento_id,)
        return None

    def fetchall(self):
        if "select texto_hash from chunk" in self._ultimo_comando:
            return self._hashes_existentes
        return []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _ConexaoFalsa:
    def __init__(self, **kwargs):
        self._cursor = _CursorFalso(**kwargs)

    def cursor(self):
        return self._cursor

    def pipeline(self):
        return contextlib.nullcontext()


def _registro(
    chunk_id: str, texto_hash: str, *, texto: str | None = None, especies=None
) -> RegistroCarga:
    # Default distinto por `texto_hash` — os testes que não mexem com
    # deduplicação continuam com um chunk por texto único; os testes de
    # fusão passam `texto=` explicitamente para forçar a colisão.
    return RegistroCarga(
        chunk_id=chunk_id,
        fonte="Spinosa et al. (2017)",
        tipo_fonte="livro",
        capitulo="20 — Anti-inflamatórios Não Esteroidais",
        pagina=410,
        farmacos=["meloxicam"],
        especies=especies if especies is not None else ["felino"],
        tokens=100,
        texto_hash=texto_hash,
        texto=texto if texto is not None else f"texto de teste {texto_hash}",
        embedding=[0.1, 0.2, 0.3],
    )


def test_calcular_indice_versao_e_deterministico_para_o_mesmo_corpus():
    a = calcular_indice_versao(["hash1", "hash2", "hash3"])
    b = calcular_indice_versao(["hash3", "hash1", "hash2"])  # ordem diferente
    assert a == b


def test_calcular_indice_versao_muda_com_o_conteudo():
    a = calcular_indice_versao(["hash1", "hash2"])
    b = calcular_indice_versao(["hash1", "hash2", "hash3"])
    assert a != b


def test_calcular_indice_versao_tem_data_e_hash():
    versao = calcular_indice_versao(["hash1"])
    assert re.fullmatch(r"\d{8}-[0-9a-f]{12}", versao)


def test_carregar_cria_documento_novo_e_insere_todos_os_chunks_novos():
    conexao = _ConexaoFalsa(documento_encontrado=None, novo_documento_id=42, hashes_existentes=())
    registros = [_registro("spinosa-c20-p410-001", "h1"), _registro("spinosa-c20-p410-002", "h2")]

    resultado = carregar(conexao, registros, titulo="Farmacologia Aplicada à Medicina Veterinária")

    assert resultado == {"inseridos": 2, "ja_existentes": 0, "fundidos": 0}
    comandos = [c for c, _params in conexao._cursor.comandos]
    assert sum("insert into documento" in c for c in comandos) == 1
    assert sum("insert into chunk" in c for c in comandos) == 2
    assert not any("update documento" in c for c in comandos)


def test_carregar_reutiliza_documento_existente_e_pula_chunk_ja_carregado():
    conexao = _ConexaoFalsa(documento_encontrado=(7,), hashes_existentes=("h2",))
    registros = [_registro("spinosa-c20-p410-001", "h1"), _registro("spinosa-c20-p410-002", "h2")]

    resultado = carregar(conexao, registros, titulo="Farmacologia Aplicada à Medicina Veterinária")

    assert resultado == {"inseridos": 1, "ja_existentes": 1, "fundidos": 0}
    comandos = [c for c, _params in conexao._cursor.comandos]
    assert not any("insert into documento" in c for c in comandos)
    assert sum("update documento" in c for c in comandos) == 1
    assert sum("insert into chunk" in c for c in comandos) == 1


def test_carregar_checa_existencia_em_uma_unica_consulta_em_lote():
    conexao = _ConexaoFalsa(documento_encontrado=(7,), hashes_existentes=())
    registros = [_registro(f"spinosa-c20-p410-{i:03d}", f"h{i}") for i in range(50)]

    carregar(conexao, registros, titulo="Farmacologia Aplicada à Medicina Veterinária")

    comandos = [c for c, _params in conexao._cursor.comandos]
    assert sum("select texto_hash from chunk" in c for c in comandos) == 1


def test_carregar_lista_vazia_nao_toca_o_banco():
    conexao = _ConexaoFalsa()
    resultado = carregar(conexao, [], titulo="Qualquer Título")
    assert resultado == {"inseridos": 0, "ja_existentes": 0, "fundidos": 0}
    assert conexao._cursor.comandos == []


def test_carregar_funde_chunks_com_texto_normalizado_identico():
    conexao = _ConexaoFalsa(documento_encontrado=(7,), hashes_existentes=())
    registros = [
        _registro(
            "meloxicam-interacoes-001",
            "h1",
            texto="Outros AINEs  podem competir.",
            especies=["canino"],
        ),
        _registro(
            "meloxicam-interacoes-002",
            "h2",
            texto="outros aines podem competir.",  # mesmo texto, só caixa/espaço diferentes
            especies=["canino", "felino"],  # ciclo mais completo — este deve ser mantido
        ),
    ]

    resultado = carregar(conexao, registros, titulo="Farmacologia Aplicada à Medicina Veterinária")

    assert resultado == {"inseridos": 1, "ja_existentes": 0, "fundidos": 1}
    comandos = conexao._cursor.comandos
    insercoes_chunk = [params for c, params in comandos if "insert into chunk" in c]
    assert len(insercoes_chunk) == 1
    assert insercoes_chunk[0][0] == "meloxicam-interacoes-002"  # o mais completo


def test_carregar_nao_funde_chunks_com_texto_clinicamente_diferente():
    conexao = _ConexaoFalsa(documento_encontrado=(7,), hashes_existentes=())
    registros = [
        _registro("meloxicam-interacoes-003", "h1", texto="Texto do ciclo cães e gatos."),
        _registro(
            "meloxicam-interacoes-004", "h2", texto="Texto do ciclo só gatos, mais uma frase."
        ),
    ]

    resultado = carregar(conexao, registros, titulo="Farmacologia Aplicada à Medicina Veterinária")

    assert resultado == {"inseridos": 2, "ja_existentes": 0, "fundidos": 0}
