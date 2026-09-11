"""Reddin GEREKCESI ajana ulasiyor mu -- gercek bir istemciyle sorulur.

NICIN VAR. Kapilar reddetmeyi ogrendi ama reddin METNI bir sure hicbir
yere varmadi. mcp 2.x'in kurali: arac `ToolError` firlatirsa mesaji
istemciye gecer, baska her istisna `UnexpectedToolError`a sarilir ve
metni maskelenir. `StoryError` duz bir RuntimeError oldugu icin ikinci
gruba dusuyordu ve ajanin gordugu tek sey suydu:

    "Error executing tool compose_slide"

Kapinin ozenle yazilmis "hangi icerik kaybolacak, yerine hangi araci
kullan" metni ajana HIC varmiyordu. Bir kapinin reddi sebebini
tasimiyorsa yalnizca bir engeldir; ajan onu "arac bozuk" diye okur ve
dogru tepki o cumleden uretilemez.

Duzeltme `server.py`de, kayit noktasinda: `@mcp.tool()` her araci
sariyor ve StoryError'i ToolError'a ceviriyor. Bu dosya o yamanin
DURDUGUNU her kosuda kanitlar.

NICIN GERCEK ISTEMCI. Yamayi in-process cagriyla sinamak yalan
soyleyebilirdi: maskeleme ARAC KATMANINDA oluyor ve dogrudan cagri o
katmandan baska bir yerden geciyor. Olculen sey, panelin ajaninin
kullandigi yolun aynisi olmali -- alt surec + stdio + MCP protokolu.
Bu yuzden kapi sunucuyu KENDI calistirdigi yorumcuyla baslatiyor.

FIKSTUR GEREKTIRMEZ. Kasitli red icin var olmayan bir dosya yolu yeter
("Dosya bulunamadi"), yani bu kapi temiz bir klonda da kosar -- fikstur
isteyen `tools/suit.py`den farki bu. Fikstur VARSA ustune bir bolum daha
kosar (compose kapisi) ve yoksa bunu YAZAR, sessizce atlamaz.

    python tools/red_mesaji.py
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import shutil
import sys
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

warnings.simplefilter("ignore")

# KOSAMADI, KOSTU-VE-DUSTU DEGIL (suit.py sozlesmesi: cikis 3).
# Istemci paketi yoksa bu kapi hukum VEREMEZ. ImportError ile cokmek
# cikis 1 uretirdi ve suit onu "kapi kaldi" diye okurdu -- yani hicbir
# sey olculmemisken bir kusur bildirilmis olurdu. Tersi de kotu:
# sessizce 0 donmek, bakilmamis bir seyi temiz gostermek.
KOSAMADI = 3
try:
    from mcp import ClientSession, StdioServerParameters      # noqa: E402
    from mcp.client.stdio import stdio_client                 # noqa: E402
except ImportError as _eksik:                                 # pragma: no cover
    ISTEMCI_YOK = str(_eksik)
else:
    ISTEMCI_YOK = ""

# Bkz. ajan_yolu.ACILMADI: sunucu acilmazsa kapi HUKUM VERMEZ, KOSAMADI
# doner. Yoksa "sunucu acilmadi"nin turettigi bulgular bagimsiz
# kusurlarmis gibi siralanir.
ACILMADI = "SUNUCU ACILMADI"

BLANK = ROOT.parent / "test" / "bos.story"


def _metin(res) -> str:
    return " ".join((getattr(b, "text", "") or "") for b in (res.content or []))


def _cozum(res):
    veri = getattr(res, "structured_content", None)
    if veri:
        return veri
    return json.loads(res.content[0].text)


async def kosu() -> list[str]:
    kusur: list[str] = []
    # SUNUCU, BU YORUMCUYLA. Konsol betigi (.venv/Scripts/storyline-mcp.exe)
    # kurulum yerine gore degisir; `-c` ile baslatmak kapiyi urunun
    # ortamina baglar, kurulumun tesadufune degil.
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from storyline_mcp.server import main; main()"],
        env=None,
    )
    # ALT SURECIN STDERR'I TAMPONLANIYOR -- YUTULMUYOR.
    #
    # Ilk surum `os.devnull` yaziyordu ve kararli durumda dogruydu:
    # sunucu kalibrasyon uyarilari basiyor ve suit'in "son satir"
    # sutununda kapinin HUKMU yerine o uyari goruunuyordu. Ama kosulsuz
    # yutmak, sunucu HIC ACILMAZSA (import hatasi, eksik bagimlilik,
    # sozdizimi kusuru) traceback'i de yutuyor ve elde yalnizca
    # "oturum baslatilamadi" kaliyor.
    #
    # Bu tam olarak bu deponun ayirdigi hal: KOSAMADI ile KOSTU-VE-DUSTU.
    # Tampon ikisini birden veriyor: basarida dusuyor, el sikisma
    # duserse geri sarilip BASILIYOR. Bir kez ve en kotu anda isiracak
    # turden bir kusurdu.
    import tempfile
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8",
                                errors="replace") as _tampon:
        async with stdio_client(params, errlog=_tampon) as (r, w):
            async with ClientSession(r, w) as s:
                try:
                    await s.initialize()
                except BaseException as _acilis:
                    # KOSAMADI, KOSTU-VE-DUSTU DEGIL. Sunucu acilmadiysa
                    # sebep alt surecin stderr'inde duruyor; tampon tam
                    # bunun icin var.
                    _tampon.seek(0)
                    _ciktisi = (_tampon.read() or "").strip()
                    print("SUNUCU ACILMADI (%s). Alt surecin stderr'i:"
                          % type(_acilis).__name__)
                    print(_ciktisi[-1500:] if _ciktisi else "  (stderr BOS)")
                    kusur.append(
                        "SUNUCU ACILMADI: %s -- red metni OLCULEMEDI "
                        "(stderr yukarida)" % type(_acilis).__name__)
                    return kusur
                araclar = await s.list_tools()
                print(f"el sikisti: {len(araclar.tools)} arac bildirildi")
                if len(araclar.tools) < 54:
                    kusur.append(f"arac sayisi dustu: {len(araclar.tools)} < 54 "
                                 f"-- kayit sarmalayicisi araclari yutuyor olabilir")

                # 1. KASITLI RED: metni GECMELI. Fikstur gerekmez.
                res = await s.call_tool("list_slides", {"path": "Z:/yok/olmayan.story"})
                metin = _metin(res)
                # YAPISAL, KELIMEYE BAGLI DEGIL -- VE BU BIR DUZELTME.
                #
                # Eski hali `"bulunamadi" in metin.lower()` idi ve
                # `package.py` o cumleyi yeniden yazdigi gun ayak
                # kirmiziya donerdi -- maskeleme hic geri gelmemis olsa
                # bile. (Olculdu: mesaj "Boyle bir dosya yok" diye
                # degistirildi, metin ISTEMCIYE VARDI ve ayak yine de
                # "MASKELENDI" dedi.)
                #
                # Olculen sey aslinda kelime GEREKTIRMIYOR: mcp 2.x
                # maskelerken TAM olarak "Error executing tool <ad>"
                # basiyor, gecirdiginde ustune ": <sebep>" ekliyor. Soru
                # su: genel kalibin DISINDA bir sey var mi.
                maske_kalibi = "Error executing tool list_slides"
                gecti = bool(metin.strip()) and metin.strip() != maske_kalibi
                print(f"kasitli red  : {'METIN GECTI' if gecti else 'MASKELENDI'} "
                      f"-> {metin[:90]}")
                if not gecti:
                    kusur.append(
                        "RED MASKELENIYOR: kasitli bir StoryError'in metni "
                        f"istemciye varmiyor (gorulen: {metin[:80]!r}). Ajan "
                        "sebebi okuyamaz, reddi 'arac bozuk' diye okur. "
                        "server.py'deki StoryError -> ToolError donusumu dusmus.")

                # 2. COMPOSE KAPISI, ucdan uca -- FIKSTUR VARSA.
                if not BLANK.exists():
                    print(f"compose kapisi: KOSMADI (fikstur yok: {BLANK}) -- "
                          f"bu bolumun sessizligi 'gecti' demek DEGIL")
                else:
                    hedef = ROOT.parent / "test" / "_canary" / "red_mesaji.story"
                    hedef.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(BLANK, hedef)
                    q = await s.call_tool("add_question", {
                        "path": str(hedef), "prompt": "Hangisi dogru?",
                        "choices": ["a", "b", "c", "d"], "correct": [1],
                        "eyebrow": "B", "in_place": True,
                        "feedback": {"correct": "E", "incorrect": "H"}})
                    slayt = _cozum(q).get("new_slide")
                    # GORSEL ISTEMEDEN yeniden beste: reddedilmeli VE sebebini
                    # soylemeli. Ikisi ayri sorudur ve ikisi de sorulur.
                    res2 = await s.call_tool("compose_slide", {
                        "path": str(hedef), "slide": slayt, "layout": "content",
                        "title": "Uzerine yaz", "body": "...", "in_place": True})
                    m2 = _metin(res2)
                    reddedildi = bool(getattr(res2, "is_error", False))
                    # IFADE DEGIL OZELLIK -- VE BU AYAK SANSLA AYAKTAYDI.
                    #
                    # Eski hali `"kaybolacak icerik" in m2 and ("katman" in
                    # m2 or "tetikleyici" in m2)` idi. O metin iki tur once
                    # BILEREK yeniden yazildi (katmanlar gitmiyor, SAHIPSIZ
                    # kaliyor); yeniden yazma girisi degistirdi, sondaki
                    # cumlecige dokunmadi ve ifade TESADUFEN hayatta kaldi.
                    # Bunu guvence altina alan hicbir sey yoktu.
                    #
                    # Buradaki soru semantik -- "red sebebini TASIYOR mu" --
                    # ve yapisal bir karsiligi yok (`neler` duzeltmesindeki
                    # gibi hesaplanmis bir sayi yok). O yuzden ifade yerine
                    # OZELLIK iddia ediliyor:
                    #   (a) mesaj genel maske kalibindan belirgin uzun
                    #   (b) kaybi adlandiran KUMEden en az biri geciyor
                    # Basarisizlik kipi boylece "yeniden yazildi -> yanlis
                    # kirmizi"dan "ici bosaltildi -> dogru kirmizi"ya kayiyor.
                    maske2 = "Error executing tool compose_slide"
                    kayip_adlari = ("katman", "tetikleyici", "sekil", "soru",
                                    "icerik")
                    sebepli = (len(m2.strip()) > len(maske2) + 40
                               and any(k in m2.lower() for k in kayip_adlari))
                    print(f"compose kapisi: {'REDDETTI' if reddedildi else 'KABUL ETTI'}, "
                          f"{'sebep VAR' if sebepli else 'sebep YOK'}")
                    if not reddedildi:
                        kusur.append(
                            "KAPI KOSMUYOR: gorsel istemeden yeniden beste "
                            "KABUL edildi -- soru etkilesimi (intrProps + "
                            "SubmitInteraction) sessizce siliniyor. Kosul "
                            "`image_area and clear` diye daralmis olabilir.")
                    elif not sebepli:
                        kusur.append(
                            f"RED SEBEPSIZ: kapi reddediyor ama neyin kaybolacagini "
                            f"soylemiyor (gorulen: {m2[:80]!r})")
    return kusur


def yerel_ayrim() -> list[str]:
    """Donusum YALNIZCA kasitli reddi cevirmeli, gercek kusuru degil.

    KAPSAM: bu kontrol IN-PROCESS. Yukaridaki stdio kosusu yamanin
    urunun yolunda durdugunu gosterir; bu ise ayrimin dogru yerden
    gectigini. Ikisi ayri sorular, ve ikincisi icin sunucu baslatmak
    gereksiz.
    """
    from storyline_mcp import server
    from storyline_mcp.package import StoryError
    from mcp.server.mcpserver.exceptions import ToolError

    kusur = []

    # KOSAMADI ILE KOSTU-VE-DUSTU AYRI OKUNUR. Sarmalayici hic yoksa
    # asagidaki cagri AttributeError ile COKER ve kapi bir yigin izi
    # basar; cikis kodu dogru olur ama okuyan kisi kapinin BOZUK
    # oldugunu sanir, oysa olcu tam da aradigi seyi bulmustur.
    sarmalayici = getattr(server, "_reddi_gecir", None)
    if sarmalayici is None:
        print("ayrim (in-process): KOSAMADI -- server._reddi_gecir YOK")
        return ["DONUSUM HIC YOK: server.py'de `_reddi_gecir` bulunamadi, "
                "yani kasitli redlerin metni maskeleniyor olmali"]

    def kasitli():
        raise StoryError("bu bir red")

    def kusurlu():
        raise KeyError("bu bir hata")

    try:
        sarmalayici(kasitli)()
        kusur.append("ayrim BOZUK: kasitli red hic firlatmiyor")
    except ToolError as e:
        if "bu bir red" not in str(e):
            kusur.append(f"ayrim BOZUK: red metni kayboldu ({e})")
    except StoryError:
        kusur.append("ayrim BOZUK: StoryError ToolError'a cevrilmiyor -- "
                     "metin maskelenir")

    try:
        sarmalayici(kusurlu)()
        kusur.append("ayrim BOZUK: gercek kusur yutuluyor")
    except ToolError:
        kusur.append("ayrim BOZUK: gercek kusur (KeyError) ToolError'a "
                     "cevriliyor -- ic ayrinti ajana sizar")
    except KeyError:
        pass
    print("ayrim (in-process): kasitli red gecer, gercek kusur maskeli "
          f"{'-- TUTUYOR' if not kusur else '-- KIRIK'}")
    return kusur


def main() -> int:
    if ISTEMCI_YOK:
        print(f"KOSAMADI: mcp istemcisi yok ({ISTEMCI_YOK}). Reddin metni "
              f"olculemedi -- bu 'gecti' DEGIL, 'bakilmadi'.")
        return KOSAMADI
    stdio_kusuru = asyncio.run(kosu())
    if any(k.startswith(ACILMADI) for k in stdio_kusuru):
        print("")
        print("KOSAMADI: sunucu acilmadi (sebep yukarida). Reddin metni "
              "olculemedi -- bu 'gecti' DEGIL, 'bakilmadi'.")
        return KOSAMADI
    kusur = stdio_kusuru + yerel_ayrim()
    if kusur:
        print("\nKAPI KALDI:")
        for k in kusur:
            print(f"  - {k}")
        return 1
    print("\nkapi gecti: kasitli red metni ajana variyor, gercek kusur maskeli")
    return 0


if __name__ == "__main__":
    # KANARYA KILIDI. Kapilar `test/_canary/` icine SABIT adli dosyalar
    # yaziyor; iki kosu ayni anda ayni dosyaya yazarsa ikisi de yanlis
    # okur ve sonuc "kostu ve dustu" gibi gorunur. Gerekce ve olcum:
    # tools/kanarya_kilit.py.
    from kanarya_kilit import korumali
    raise SystemExit(korumali(main))
