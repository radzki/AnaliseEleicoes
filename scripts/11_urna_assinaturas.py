"""Verify the digital signatures of the runoff files of the voting machines in the log sample (07) and recount
their votes. For every section of results/urna_logs_sample.csv, round 2 (pleito 3221), take from the TSE results
site the file set whose status is "Totalizado" (boletim de urna -bu.dat, registro digital do voto -rdv.dat, log
-log.jez, signature file -vota.vsc) and:
  1. check, as TSE's own example scripts do, that the SHA-512 of each file equals the one listed in the signature
     file and that the machine's hardware signature over it is valid; that the machine certificate carried in the
     signature file was signed by a TSE certification authority (CA) whose certificate comes from TSE's
     documentation, not from the downloaded files; and the hash chain and signature over the BU vote tuples;
  2. decode the BU and compare its presidential counts with the published section results (secao_wide.parquet);
  3. decode the RDV, recount its votes one by one and compare with the BU.

Usage: python -I scripts/11_urna_assinaturas.py <processed_2026> <cache_dir> <out_dir>

Sources (TSE). Page "Documentação técnica do software da urna eletrônica"
(https://www.tse.jus.br/eleicoes/eleicoes-2022/documentacao-tecnica-do-software-da-urna-eletronica): ASN.1 of the BU,
RDV and signature file, plus Python examples. The current package, formato-arquivos-bu-rdv-ass-digital-v2.zip (files
dated 25/09/2024; it already describes the 2026 names -bu.dat / -rdv.dat / -vota.vsc), SHA-256 1e423054...a235.
tse.jus.br answers 403 to scripts, so the zip comes from the public mirror github.com/doccaz/urnas-br (docv2/, commit
6026afb) and must match that hash, which other independent copies (alissonlinneker/DataUrnas-BR,
marvinbraga/eleicoes_brasil_tse_download) report too. Used from it: spec/bu.asn1, spec/rdv.asn1,
spec/assinatura.asn1; the procedures of python/assinatura_hash.py (file hashes and signatures, machine certificate),
python/bu_assinatura_tuplas.py (BU tuple chain) and python/lib/mr_util.py, whose constant _AC_RAIZ_UE_PEMS holds the
certificates of the three issuing CAs ("obtidos em dpc.acue2020.tse.jus.br"). Those Python files are read as text,
never run. Libraries as in TSE's README: asn1tools, and ECPy from source (no ECPy release has the Ed521 curve);
certificates are parsed with cryptography instead of TSE's pyOpenSSL.

Chain of trust. The urna's hardware key (UE2020/UE2022: Ed521, EdDSA with SHAKE-256; UE2009-UE2015: ECDSA P-521)
signs SHA-512(SHA-512 of each file). Its certificate travels inside -vota.vsc, so on its own it proves nothing; it
counts because it is signed by AC UE2020, AC UE2022 or AC URNA, whose certificates come from TSE's documentation
package. AC UE2020's and AC UE2022's certificates also match, byte for byte as PEM, the SHA-512 that TSE's "resumo
digital" of the HOLOCRON system (Eleições 2026, 02/09/2026) lists for acue2020.cer / acue2022.cer. Those values are
transcribed below from alissonlinneker/DataUrnas-BR because the TSE original could not be fetched. AC URNA is not in
that summary, and its published certificate expired on 18/07/2026, before the election. The roots above them (AC RAIZ
UE, AC RAIZ UE v2, AC URNA v2) are not downloadable (dpc.acue2020.tse.jus.br answers 403), so the chain stops at the
issuing CA. A browser-downloaded copy placed in <cache_dir>/tse/ac/ is checked against the HOLOCRON hash and used to
climb further. The software signature (assinaturaSW) uses CEPESC, a government algorithm with no public
specification or key: its file hashes are checked, its signature is not verifiable.

The 2026 -vota.vsc differs from the published v2 spec in two places, handled below:
  - the top level is SEQUENCE {assinaturaSW, assinaturaHW, SEQUENCE {modeloEquipamento, algoritmoAssinatura}}
    rather than v2's SEQUENCE {modeloEquipamento, assinaturaSW, assinaturaHW};
  - in EntidadeAssinatura, conjuntoChave and certificadoDigital now carry context tags [0] and [1], which a v2
    decoder skips without error, losing the certificate;
  - also, many DER certificates of UE2009-UE2015 end with one to three zero bytes of padding, trimmed here (TSE's
    pyOpenSSL ignores them).
And one gap in TSE's tuple script: for a contingency machine that took over a section (tipoUrna 4), the BU names only
the machine's own municipality and zone where the script reads the seed; the stored hashes show the chain is seeded
with the section the machine served (identificacaoSecao: municipality, zone and section).
"""
import base64
import collections
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import textwrap
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import asn1tools
import pandas as pd
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from ecpy.curves import Curve
from ecpy.ecdsa import ECDSA
from ecpy.eddsa import EDDSA
from ecpy.keys import ECPublicKey

proc, cache, out = (Path(a) for a in sys.argv[1:4])
sys.stdout.reconfigure(encoding="utf-8")
cache.mkdir(parents=True, exist_ok=True)
BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados"
PLEITO = 3221
SEC = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
DAY = dt.datetime(2026, 10, 25, 12, tzinfo=dt.timezone.utc)
LOG07 = cache.parent / "urna_logs"  # logs already downloaded by 07 (same rule: first "Totalizado" set)

ZIP_NAME = "formato-arquivos-bu-rdv-ass-digital-v2.zip"
ZIP_SHA256 = "1e423054f32b8ba056960c58ada167d702c2618cc4d1dfd5de88f5090c84a235"
ZIP_URL = ("https://raw.githubusercontent.com/doccaz/urnas-br/6026afb61338dbb8ff13334fb056095882198aa4/docv2/"
           + ZIP_NAME)
# SHA-512 (base64) of the CA files in TSE's resumo digital of HOLOCRON, Eleições 2026 (header "HOLOCRON -
# 02/09/2026", folder D:\Aplic\SEVIN\Holocron\certificados), as transcribed in alissonlinneker/DataUrnas-BR,
# scripts/ele2026/analisar_certificados.py.
HOLOCRON = {
    "O/LBooMqsk+Zx//zxVwXr0lboFIPwvgVj/nILBlZQaC+HZtQ1PuAFEdaWga458oPijiuUl5umAjVO+2bIcgt0g==": "acraiz-ue.pem",
    "2a/T+2kuy0njwNLrSgqlAkala9p7FF6PL8x3327/M+xY9RHeQTytbeSSBEqib40aFS0q0Ir9HuL0LVwhRi6ozw==": "acraizuev2.cer",
    "OTL7MHgqDbasQvSjBMWk5SkqBf5UTV7V3YjQ/kWqe8ZYZfayRLLJRJAtnS9USj4MIVg5ejiWM5ZGKiAJ1usOgw==": "acurnav2.cer",
    "LLveJWbhgUEiPfm/WlQL2b1Y0UtSdzvLlKB+tDAhM60rQ869y7/iEw3yQKSkMKVVN3goJsmB/m21MASvdxKhzg==": "acue2020.cer",
    "nawawQDNRHwS4X5kYuMNZhn+aTv/ZDxzdIhbMP0mQ6rqGZ6Q5YkiTjeRSmhEEUztze7D94pBvHQAkXdI28eYeQ==": "acue2022.cer",
}
OID_ED521, OID_EC, OID_P521 = "1.3.6.1.4.1.44588.2.1", "1.2.840.10045.2.1", "1.3.132.0.35"
ROLE = {"bu": "bu", "busa": "bu", "rdv": "rdv", "rdvred": "rdv", "log": "log", "logsa": "log",
        "vota": "vsc", "red": "vsc", "sa": "vsc"}
MODEL = {9: "UE2009", 10: "UE2010", 11: "UE2011", 13: "UE2013", 15: "UE2015", 20: "UE2020", 22: "UE2022"}


# ---------------------------------------------------------------------------------
# Download (cached), as in 07
def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 ** i)
        except Exception:
            time.sleep(2 ** i)
    return None


# ---------------------------------------------------------------------------------
# TSE's package: ASN.1 modules and the certificates of the issuing CAs (read as text, not executed)
zpath = cache / "tse" / ZIP_NAME
if not zpath.exists():
    data = get(ZIP_URL)
    if not data:
        sys.exit(f"could not download {ZIP_URL}")
    zpath.parent.mkdir(parents=True, exist_ok=True)
    zpath.write_bytes(data)
if hashlib.sha256(zpath.read_bytes()).hexdigest() != ZIP_SHA256:
    sys.exit(f"{zpath}: SHA-256 differs from TSE's package, refusing to use it")
zf = zipfile.ZipFile(zpath)
ztext = {Path(n).name: zf.read(n).decode("utf-8") for n in zf.namelist()
         if n.endswith((".asn1", "mr_util.py"))}

# The 2026 layout of -vota.vsc (see docstring), written with the v2 module's own types.
VSC2026 = """
Assinatura2026 DEFINITIONS IMPLICIT TAGS ::= BEGIN
IMPORTS DataHoraJE, AutoAssinaturaDigital, ModeloEquipamento, AlgoritmoAssinatura FROM ModuloAssinaturaResultado;
EntidadeAssinatura2026 ::= SEQUENCE {
    dataHoraCriacao DataHoraJE, versao INTEGER, autoAssinado AutoAssinaturaDigital, conteudoAutoAssinado OCTET STRING,
    conjuntoChave [0] GeneralString OPTIONAL, certificadoDigital [1] OCTET STRING OPTIONAL }
EntidadeAssinaturaEcourna2026 ::= SEQUENCE {
    assinaturaSW EntidadeAssinatura2026, assinaturaHW EntidadeAssinatura2026,
    equipamento SEQUENCE { modeloEquipamento ModeloEquipamento, algoritmoAssinatura AlgoritmoAssinatura } }
END
"""
BU = asn1tools.compile_string(ztext["bu.asn1"], codec="ber", numeric_enums=True)
RDV = asn1tools.compile_string(ztext["rdv.asn1"], codec="ber", numeric_enums=True)
ASS = asn1tools.compile_dict({**asn1tools.parse_string(ztext["assinatura.asn1"]), **asn1tools.parse_string(VSC2026)},
                             codec="ber", numeric_enums=True)
# Enough of RFC 5280 to reach the subject public key, whatever its algorithm (cryptography does not know Ed521).
X509 = asn1tools.compile_string("""X DEFINITIONS ::= BEGIN
Cert ::= SEQUENCE { tbs TBS, alg ANY, sig BIT STRING }
TBS ::= SEQUENCE { version [0] EXPLICIT INTEGER OPTIONAL, serial INTEGER, sigalg ANY, issuer ANY, validity ANY,
    subject ANY, spki SEQUENCE { alg SEQUENCE { algorithm OBJECT IDENTIFIER, parameters ANY OPTIONAL }, key BIT STRING },
    issuerUID [1] IMPLICIT BIT STRING OPTIONAL, subjectUID [2] IMPLICIT BIT STRING OPTIONAL,
    extensions [3] EXPLICIT ANY OPTIONAL }
END""", codec="der")
CURVES = {OID_ED521: Curve.get_curve("Ed521"), OID_EC: Curve.get_curve("secp521r1")}


def cn(name):
    v = name.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    return v[0].value if v else name.rfc4514_string()


def pubkey(cert):
    """(algorithm OID, ECPy public key) of a certificate, as mr_util.extrai_chave_do_certificado."""
    spki = X509.decode("Cert", cert.public_bytes(Encoding.DER))["tbs"]["spki"]
    oid = spki["alg"]["algorithm"]
    if oid == OID_EC and spki["alg"].get("parameters") != bytes.fromhex("06052b81040023"):  # secp521r1
        raise ValueError("EC key not on P-521")
    return oid, ECPublicKey(CURVES[oid].decode_point(spki["key"][0]))


def verify(key, msg, sig):
    """ECPy verification exactly as TSE calls it: `msg` is what TSE passes (ECDSA takes it as the digest)."""
    oid, k = key
    try:
        v = EDDSA(hashlib.shake_256, hash_len=132) if oid == OID_ED521 else ECDSA()
        return bool(v.verify(msg, sig, k))
    except Exception:
        return False


def cert_signed_by(cert, key):
    """mr_util.valida_certificado: EdDSA over the TBS; ECDSA over SHA-512(TBS)."""
    tbs = cert.tbs_certificate_bytes
    return verify(key, tbs if key[0] == OID_ED521 else hashlib.sha512(tbs).digest(), cert.signature)


def pem(cert):
    b64 = base64.b64encode(cert.public_bytes(Encoding.DER)).decode()
    return ("-----BEGIN CERTIFICATE-----\n" + "\n".join(textwrap.wrap(b64, 64)) + "\n-----END CERTIFICATE-----\n").encode()


def holocron(cert, raw=None):
    for b in filter(None, (raw, pem(cert))):
        h = base64.b64encode(hashlib.sha512(b).digest()).decode()
        if h in HOLOCRON:
            return HOLOCRON[h]
    return ""


# Issuing CAs from mr_util.py, plus any root/intermediate the user drops in <cache>/tse/ac/ (e.g. downloaded by hand
# from dpc.acue2020.tse.jus.br).
mr = ztext["mr_util.py"]
mr = mr[mr.index("_AC_RAIZ_UE_PEMS = ["):]
CAS = [x509.load_der_x509_certificate(base64.b64decode("".join(b.split())))
       for _, b in re.findall(r'#\s*(\S+)\s*\n\s*"""\s*(.*?)"""', mr, re.S)]
EXTRA = {}
for p in sorted((cache / "tse" / "ac").glob("*")) if (cache / "tse" / "ac").is_dir() else []:
    raw = p.read_bytes()
    try:
        c = x509.load_pem_x509_certificate(raw) if raw.lstrip().startswith(b"-----") else x509.load_der_x509_certificate(raw)
    except ValueError:
        continue
    EXTRA[c.subject] = (c, holocron(c, raw), p.name)


def climb(c):
    """Walk up from a CA certificate through the extra certificates whose signature verifies."""
    path = []
    while c.issuer != c.subject and c.issuer in EXTRA:
        up, holo, _ = EXTRA[c.issuer]
        if not cert_signed_by(c, pubkey(up)):
            path.append(f"{cn(up.subject)}: SIGNATURE FAILS")
            break
        path.append(cn(up.subject) + (f" (HOLOCRON {holo})" if holo else " (not in HOLOCRON)"))
        c = up
    top = "root" if c.issuer == c.subject else f"stops below {cn(c.issuer)} (not available)"
    return " -> ".join(path), top


CA = {}
print("Issuing CAs (from TSE's documentation package):")
for c in CAS:
    up, top = climb(c)
    CA[c.subject] = {"cert": c, "key": pubkey(c), "name": cn(c.subject),
                     "valid_day": c.not_valid_before_utc <= DAY <= c.not_valid_after_utc, "chain": up, "top": top}
    print(f"  {cn(c.subject)}: issued by {cn(c.issuer)}, valid {c.not_valid_before_utc:%d/%m/%Y}-"
          f"{c.not_valid_after_utc:%d/%m/%Y}, HOLOCRON 2026 summary: {holocron(c) or 'not listed'}; "
          f"chain above: {up or '-'} [{top}]")
for subj, (c, holo, fn) in EXTRA.items():
    print(f"  extra certificate {fn}: {cn(subj)}, HOLOCRON: {holo or 'NOT LISTED'}")


# ---------------------------------------------------------------------------------
# Sample and published results
sample = pd.read_csv(out / "urna_logs_sample.csv", usecols=[*SEC, "group"])
w = pd.read_parquet(proc / "secao_wide.parquet", columns=["NR_TURNO", "CD_CARGO", *SEC, "QT_APTOS", "QT_COMPARECIMENTO",
                                                           "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS", "v13", "v22",
                                                           "DS_MODELO_URNA"])
w = w[(w.NR_TURNO == 2) & (w.CD_CARGO == 1)].drop(columns=["NR_TURNO", "CD_CARGO"])
pub = {tuple(r[:4]): r for r in w.itertuples(index=False, name=None)}
PUB_COLS = list(w.columns[4:])
print(len(sample), "sections in the sample", flush=True)


# ---------------------------------------------------------------------------------
# Per section: fetch the "Totalizado" set, verify, decode, recount
def fetch(r, rec, reuse07=True):
    uf, mu, zn, se = r.SG_UF.lower(), f"{r.CD_MUNICIPIO:05d}", f"{r.NR_ZONA:04d}", f"{r.NR_SECAO:04d}"
    d = cache / uf / f"{mu}-{zn}-{se}"
    url = f"{BASE}/{uf}/{mu}/{zn}/{se}"
    auxp = d / "aux.json"
    # the CDN can serve stale copies of the file list: bust its cache (the data files are addressed by hash)
    aux = auxp.read_bytes() if auxp.exists() else get(f"{url}/p003221-{uf}-m{mu}-z{zn}-s{se}-aux.json?v={int(time.time())}")
    if not aux:
        rec["fileset"] = "no aux.json"
        return {}
    meta = json.loads(aux)
    sets = meta.get("hashes", [])
    rec["sets"] = "|".join(f"{h.get('st', '?')} {h.get('dr', '')} {h.get('hr', '')}" for h in sets)
    tot = [h for h in sets if h.get("st") == "Totalizado"]
    if not tot:
        rec["fileset"] = "no Totalizado set"
        return {}
    d.mkdir(parents=True, exist_ok=True)
    auxp.write_bytes(aux)  # cached only once totalized
    h = tot[0]
    rec["fileset"] = "Totalizado"
    files = {}
    for a in h["arq"]:
        role = ROLE.get(a["tp"])
        if role is None:
            rec["other_files"] = (rec.get("other_files", "") + " " + a["nm"]).strip()
            continue
        p = d / a["nm"]
        if not p.exists():
            old = LOG07 / uf / f"{mu}-{zn}-{se}-log.jez"
            if role == "log" and reuse07 and old.exists():
                shutil.copyfile(old, p)
                files["log07"] = True
            else:
                data = get(f"{url}/{h['hash']}/{a['nm']}")
                if data is None:
                    continue
                p.write_bytes(data)
        files[role] = p
    rec["files"] = ",".join(k for k in ("bu", "rdv", "log", "vsc") if k in files)
    return files


def decode_vsc(raw):
    try:
        v = ASS.decode("EntidadeAssinaturaEcourna2026", raw)
        return v["assinaturaSW"], v["assinaturaHW"], v["equipamento"]["modeloEquipamento"], "2026"
    except Exception:
        v = ASS.decode("EntidadeAssinaturaEcourna", raw)  # published v2 layout
        return v["assinaturaSW"], v["assinaturaHW"], v["modeloEquipamento"], "v2"


def load_cert(b):
    if b.lstrip().startswith(b"-----BEGIN"):
        return x509.load_pem_x509_certificate(b), ""
    n = b[1] & 0x7F if b[1] & 0x80 else 0
    size = 2 + n + (int.from_bytes(b[2:2 + n], "big") if n else b[1])
    return x509.load_der_x509_certificate(b[:size]), (f"{len(b) - size} trailing byte(s)" if len(b) > size else "")


def check_signatures(files, rec, problems):
    """assinatura_hash.py: SHA-512 of each file vs. both lists; hardware signature over SHA-512(hash); certificate."""
    sw, hw, model, layout = decode_vsc(files["vsc"].read_bytes())
    rec.update(model=MODEL.get(model, model), vsc_layout=layout,
               hw_alg={2: "ECDSA P-521", 4: "Ed521"}.get(hw["autoAssinado"]["algoritmoAssinatura"]["algoritmo"], "?"),
               sw_alg={3: "CEPESC"}.get(sw["autoAssinado"]["algoritmoAssinatura"]["algoritmo"], "?"))
    if "certificadoDigital" not in hw:
        problems.append("no certificate in vota.vsc")
        return None
    cert, note = load_cert(hw["certificadoDigital"])
    key = pubkey(cert)
    rec.update(cert_cn=cn(cert.subject), cert_issuer=cn(cert.issuer), cert_note=note,
               cert_valid_day=cert.not_valid_before_utc <= DAY <= cert.not_valid_after_utc)
    ca = CA.get(cert.issuer)
    if ca is None:
        rec["cert_ok"] = "unknown issuer"
    else:
        rec.update(cert_ok=cert_signed_by(cert, ca["key"]), ca_valid_day=ca["valid_day"], chain_top=ca["top"])
        if not rec["cert_ok"]:
            problems.append(f"certificate not signed by {ca['name']}")
    lists = {}
    for nm, e in (("sw", sw), ("hw", hw)):
        auto = e["autoAssinado"]["assinatura"]
        rec[f"{nm}_self_hash"] = hashlib.sha512(e["conteudoAutoAssinado"]).digest() == auto["hash"]
        lists[nm] = {a["nomeArquivo"]: a["assinatura"] for a in ASS.decode("Assinatura", e["conteudoAutoAssinado"])["arquivosAssinados"]}
    auto = hw["autoAssinado"]["assinatura"]
    rec["vsc_self_sig"] = verify(key, hashlib.sha512(auto["hash"]).digest(), auto["assinatura"])
    rec["n_signed_files"] = len(lists["hw"])
    for role in ("bu", "rdv", "log"):
        if role not in files:
            continue
        digest = hashlib.sha512(files[role].read_bytes()).digest()
        s_hw, s_sw = lists["hw"].get(files[role].name), lists["sw"].get(files[role].name)
        if s_hw is None:
            rec[f"sig_{role}"] = "not listed"
            problems.append(f"{role} not listed in vota.vsc")
            continue
        rec[f"hash_{role}"] = digest == s_hw["hash"] and s_sw is not None and digest == s_sw["hash"]
        rec[f"sig_{role}"] = verify(key, hashlib.sha512(s_hw["hash"]).digest(), s_hw["assinatura"])
        if role == "bu":  # negative control: one flipped bit must fail
            bad = bytes([s_hw["hash"][0] ^ 1]) + s_hw["hash"][1:]
            rec["tamper_rejected"] = not verify(key, hashlib.sha512(bad).digest(), s_hw["assinatura"])
    for k in ("sw_self_hash", "hw_self_hash", "vsc_self_sig", "hash_bu", "hash_rdv", "hash_log", "sig_bu", "sig_rdv",
              "sig_log", "tamper_rejected"):
        if rec.get(k) is False:
            problems.append(f"{k} failed")
    return key


def bu_tuples(bu, key):
    """bu_assinatura_tuplas.py: SHA-512 chain over the vote tuples of each election, then its signature."""
    cr = bu["urna"]["correspondenciaResultado"]
    # A contingency machine (identificacaoContingencia) names only its own municipality and zone here, and TSE's
    # script stops with KeyError; its chain is seeded with the section it served (identificacaoSecao), as the stored
    # hashes show.
    ident = cr["identificacao"]
    mzs = ident[1] if ident[0] == "identificacaoSecaoEleitoral" else bu["identificacaoSecao"]
    ok_chain = ok_sig = True
    for e in bu["resultadosVotacaoPorEleicao"]:
        t = (f"{bu['cabecalho']['idEleitoral'][1]:05}|{e['idEleicao']:05}|{mzs['municipioZona']['municipio']:05}|"
             f"{mzs['municipioZona']['zona']:04}|{mzs['secao']:04}|{cr['carga']['codigoCarga']:24}")
        h = hashlib.sha512(t.encode("iso8859-1")).digest().hex().upper()
        for rv in e["resultadosVotacao"]:
            for tc in rv["totaisVotosCargo"]:
                for o, v in enumerate(tc["votosVotaveis"], 1):
                    iv = v.get("identificacaoVotavel")
                    t = f"{h}|{o}|{tc['codigoCargo'][1]}|{v['tipoVoto']}|{v['quantidadeVotos']}"
                    t += f"|{iv['codigo']}|{iv['partido']}" if iv else ""
                    h = hashlib.sha512(t.encode("iso8859-1")).digest().hex().upper()
                    ok_chain &= h == v["hash"].hex().upper() and o == v["ordemGeracaoHash"]
        ok_chain &= h == e["ultimoHashVotosVotavel"].hex().upper()
        if key is not None:
            ok_sig &= verify(key, hashlib.sha512(bytes.fromhex(h)).digest(), e["assinaturaUltimoHashVotosVotavel"])
    return ok_chain, (ok_sig if key is not None else None)


def same_section(ident, r):
    mz = ident["municipioZona"]
    return (mz["municipio"], mz["zona"], ident["secao"]) == (r.CD_MUNICIPIO, r.NR_ZONA, r.NR_SECAO)


def read_bu(path, r, rec, problems, key):
    env = BU.decode("EntidadeEnvelopeGenerico", path.read_bytes())
    bu = BU.decode("EntidadeBoletimUrna", env["conteudo"])
    rec.update(bu_pleito=bu["cabecalho"]["idEleitoral"][1], bu_fase=bu["fase"], bu_tipo_urna=bu["urna"]["tipoUrna"],
               bu_tipo_arquivo=bu["urna"]["tipoArquivo"], urna_num=bu["urna"]["correspondenciaResultado"]["carga"]["numeroInternoUrna"])
    if bu["cabecalho"]["idEleitoral"] != ("idPleito", PLEITO) or bu["fase"] != 2 or not same_section(bu["identificacaoSecao"], r):
        problems.append(f"BU is not pleito {PLEITO} / oficial / this section")
    if rec.get("cert_cn"):
        rec["urna_matches_cert"] = int(re.sub(r"\D", "", rec["cert_cn"]) or -1) == rec["urna_num"]
    rec["bu_tuple_chain"], rec["bu_tuple_sig"] = bu_tuples(bu, key)
    if rec["bu_tuple_chain"] is False or rec["bu_tuple_sig"] is False:
        problems.append("BU tuple chain/signature failed")
    for e in bu["resultadosVotacaoPorEleicao"]:
        for rv in e["resultadosVotacao"]:
            for tc in rv["totaisVotosCargo"]:
                if tc["codigoCargo"] != ("cargoConstitucional", 1):
                    continue
                c = collections.Counter()
                for v in tc["votosVotaveis"]:  # BU TipoVoto: 1 nominal, 2 blank, 3 null, 4 party, 5 no candidate
                    t, code = v["tipoVoto"], v.get("identificacaoVotavel", {}).get("codigo")
                    c[{13: "13", 22: "22"}.get(code, "outro") if t == 1 else {2: "branco", 3: "nulo"}.get(t, "outro")] \
                        += v["quantidadeVotos"]
                rec.update(bu_eleicao=e["idEleicao"], bu_aptos=e["qtdEleitoresAptos"], bu_comparecimento=rv["qtdComparecimento"],
                           bu_13=c["13"], bu_22=c["22"], bu_branco=c["branco"], bu_nulo=c["nulo"], bu_outro=c["outro"])
                return
    problems.append("no presidential race in the BU")


def read_rdv(path, r, rec, problems):
    rdv = RDV.decode("EntidadeResultadoRDV", path.read_bytes())["rdv"]
    if rdv["pleito"] != PLEITO or rdv["fase"] != 2 or not same_section(rdv["identificacao"], r):
        problems.append(f"RDV is not pleito {PLEITO} / oficial / this section")
    for el in rdv["eleicoes"][1]:
        for vc in el["votosCargos"]:
            if vc["idCargo"] != ("cargoConstitucional", 1):
                continue
            c = collections.Counter()
            for v in vc["votos"]:  # RDV TipoVoto: 2 nominal; 3, 5 blank; 4, 6-9 null; 1 party (none here)
                t = v["tipoVoto"]
                c[{"13": "13", "22": "22"}.get(v.get("digitacao"), "outro") if t == 2 else
                  "branco" if t in (3, 5) else "nulo" if t in (4, 6, 7, 8, 9) else "outro"] += 1
            rec.update(rdv_eleicao=el["idEleicao"], rdv_votos=len(vc["votos"]), rdv_13=c["13"], rdv_22=c["22"],
                       rdv_branco=c["branco"], rdv_nulo=c["nulo"], rdv_outro=c["outro"])
            return
    problems.append("no presidential race in the RDV")


def compare(rec, r):
    p = pub.get((r.SG_UF, r.CD_MUNICIPIO, r.NR_ZONA, r.NR_SECAO))
    if "bu_13" in rec:
        if p is None:
            rec["bu_vs_pub"] = "no published row"
        else:
            p = dict(zip(PUB_COLS, p[4:]))
            rec.update({f"pub_{k}": p[c] for k, c in (("aptos", "QT_APTOS"), ("comparecimento", "QT_COMPARECIMENTO"),
                                                        ("13", "v13"), ("22", "v22"), ("branco", "QT_VOTOS_BRANCOS"),
                                                        ("nulo", "QT_VOTOS_NULOS"))}, pub_modelo=p["DS_MODELO_URNA"])
            diff = [f"{k} BU {rec[f'bu_{k}']} vs pub {rec[f'pub_{k}']}"
                    for k in ("aptos", "comparecimento", "13", "22", "branco", "nulo")
                    if pd.isna(rec[f"pub_{k}"]) or int(rec[f"bu_{k}"]) != int(rec[f"pub_{k}"])]
            diff += [f"outro BU {rec['bu_outro']}"] if rec["bu_outro"] else []
            rec["bu_vs_pub"] = "match" if not diff else "mismatch: " + "; ".join(diff)
    if "bu_13" in rec and "rdv_13" in rec:
        diff = [f"{k} RDV {rec[f'rdv_{k}']} vs BU {rec[f'bu_{k}']}" for k in ("13", "22", "branco", "nulo", "outro")
                if rec[f"rdv_{k}"] != rec[f"bu_{k}"]]
        if rec["rdv_votos"] != rec["bu_comparecimento"]:
            diff.append(f"RDV votes {rec['rdv_votos']} vs BU turnout {rec['bu_comparecimento']}")
        if rec["rdv_eleicao"] != rec["bu_eleicao"]:
            diff.append(f"election id RDV {rec['rdv_eleicao']} vs BU {rec['bu_eleicao']}")
        rec["rdv_vs_bu"] = "match" if not diff else "mismatch: " + "; ".join(diff)


def work(r):
    rec = {**{k: getattr(r, k) for k in SEC}, "group": r.group}
    problems = []
    files = fetch(r, rec)
    key = None
    try:
        if "vsc" in files:
            key = check_signatures(files, rec, problems)
            if rec.get("hash_log") is False and files.get("log07"):  # 07's copy is not this set's log: fetch it
                files["log"].unlink()
                files, problems = fetch(r, rec, reuse07=False), []
                key = check_signatures(files, rec, problems)
        if "bu" in files:
            read_bu(files["bu"], r, rec, problems, key)
        if "rdv" in files:
            read_rdv(files["rdv"], r, rec, problems)
        compare(rec, r)
    except Exception as e:
        problems.append(f"decode error: {type(e).__name__}: {e}")
    checks = [rec.get(k) for k in ("cert_ok", "hash_bu", "hash_rdv", "hash_log", "sig_bu", "sig_rdv", "sig_log",
                                   "sw_self_hash", "hw_self_hash", "vsc_self_sig", "bu_tuple_chain", "bu_tuple_sig",
                                   "tamper_rejected")]
    if not files:
        rec["signatures"] = "missing"
    elif any(c is False for c in checks) or any(rec.get(f"sig_{k}") == "not listed" for k in ("bu", "rdv", "log")):
        rec["signatures"] = "invalid"
    elif all(c is True for c in checks):
        rec["signatures"] = "valid"
    else:
        rec["signatures"] = "unverifiable"
    rec["sw_signature"] = "unverifiable (CEPESC)" if rec.get("sw_alg") == "CEPESC" else rec.get("sw_alg", "")
    rec["problems"] = "; ".join(problems)
    return rec


t0 = time.time()
recs = []
with cf.ThreadPoolExecutor(4) as ex:
    for i, rec in enumerate(ex.map(work, sample.itertuples(index=False)), 1):
        recs.append(rec)
        if i % 100 == 0:
            print(f"{i}/{len(sample)} ({time.time() - t0:.0f} s)", flush=True)

res = pd.DataFrame(recs).convert_dtypes()
res.to_csv(out / "urna_assinaturas.csv", index=False)

# ---------------------------------------------------------------------------------
# Summary
n = len(res)
has = lambda c: res[c] if c in res else pd.Series([None] * n)
vc = lambda s: {str(k): int(v) for k, v in s.value_counts(dropna=False).items()}
print(f"\nsections attempted: {n} | with a 'Totalizado' file set: {(has('fileset') == 'Totalizado').sum()} | "
      f"all four files (BU, RDV, log, vota.vsc): {(has('files') == 'bu,rdv,log,vsc').sum()}")
print("file set:", vc(has("fileset")))
print("signatures:", vc(res.signatures),
      "(valid = file hashes, hardware signatures of BU/RDV/log/vsc, BU tuple chain and signature, machine certificate"
      " signed by the TSE issuing CA; the CEPESC software signature is not verifiable)")
for c in ("model", "hw_alg", "cert_issuer", "cert_ok", "cert_valid_day", "ca_valid_day", "chain_top", "urna_matches_cert",
          "vsc_layout", "cert_note", "tamper_rejected", "bu_tipo_urna", "bu_tipo_arquivo"):
    if c in res:
        print(f"  {c}:", vc(res[c]))
bvp = has("bu_vs_pub").fillna("not decoded")
rvb = has("rdv_vs_bu").fillna("not decoded")
print("BU == published data:", (bvp == "match").sum(), "| mismatch:", bvp.str.startswith("mismatch").sum(),
      "| other:", vc(bvp[~bvp.eq("match") & ~bvp.str.startswith("mismatch")]))
print("RDV recount == BU:", (rvb == "match").sum(), "| mismatch:", rvb.str.startswith("mismatch").sum(),
      "| other:", vc(rvb[~rvb.eq("match") & ~rvb.str.startswith("mismatch")]))
bad = res[(res.signatures != "valid") | ~bvp.eq("match") | ~rvb.eq("match") | has("problems").fillna("").ne("")]
print(f"\nsections with any failure or mismatch: {len(bad)}")
for i, b in bad.iterrows():
    print(f"  {b.SG_UF} {b.CD_MUNICIPIO:05d}/{b.NR_ZONA:04d}/{b.NR_SECAO:04d} [{b.group}] files={b.get('files')} "
          f"sets={b.get('sets')} signatures={b.signatures} bu_vs_pub={bvp[i]} rdv_vs_bu={rvb[i]} problems={b.problems}")
print(f"\n{time.time() - t0:.0f} s")
