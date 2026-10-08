# Database — MVP Part 2

PostgreSQL persistence temeli: Python 3.11+, SQLAlchemy 2.0, psycopg 3 ve Alembic.
Standalone çalışır; NetWorth koduna veya database'ine dependency yoktur.

## Modeller ve sınırlar

- **Instrument ≠ Position.** `instruments` global enstrüman kimliğini tutar: UUID,
  symbol, name, instrument_type, nullable venue, currency ve timestamps.
  Quantity, average cost, portfolio weight ve P&L içermez.
- **IntelligenceState current state'tir.** `intelligence_states.instrument_id`
  hem primary key hem foreign key'dir: instrument başına en fazla bir state.
  Instrument state olmadan da oluşturulabilir. History bağlantısı yoksa instrument
  silinince current state silinir; history bağlantıları instrument silmeyi engeller.
- Thesis, valuation, technical ve recommendation ayrı typed enum'lardır;
  PostgreSQL native enum ve SQLAlchemy write validation kullanılır. İlk durumda
  state/review alanları `NULL` olabilir; `NULL` olumlu/neutral sonuç anlamına gelmez.
- Persistent datetime contract **UTC**'dir. Naive datetime kabul edilmez:
  SQLAlchemy typed insert/update sırasında (ORM flush dahil) reddedilir.
  Aware girdiler UTC'ye normalize edilir; okunan değerler UTC döner. Application
  engine bağlantıları `TimeZone=UTC` kullanır; PostgreSQL kolonları native
  `timestamptz` olarak kalır. Untyped raw SQL bu Python doğrulamasını çalıştırmaz;
  doğrudan SQL yazan caller da timezone-aware/UTC sözleşmesine uymalıdır.
  `created_at`/`updated_at` database default'u alır;
  SQLAlchemy üzerinden update, `updated_at` alanını yeniler. Doğrudan SQL yazan
  caller `updated_at` alanını kendisi güncellemelidir.
- Current IntelligenceState için confidence standardı açık olduğundan alan eklenmedi. Instrument type ve currency
  text tutulur; yeni taxonomy dayatılmaz. Instrument identity şu aşamada UUID
  tabanlıdır. Global symbol uniqueness intentionally yoktur; farklı venue/type'larda
  tekrar edebilir. Duplicate real-world instrument resolution ileride
  ingestion/provider katmanında ele alınacaktır.
- Provider, services, context builder, AI execution, scheduler ve UI yoktur.

## History modelleri

| Model | Rol |
|---|---|
| IntelligenceState | Instrument'ın latest compact current state'i |
| ProtocolRun | Generic protocol execution history; instrument nullable, portfolio-level run desteklenir |
| ResearchArtifact | Filesystem'deki detailed evidence/report için referans ve version kaydı |
| TechnicalPlan | Instrument'a ait technical strategy ve geçmiş planlar |

`ProtocolRun`: `RUNNING` başlangıç durumudur; sonuç `COMPLETED` veya `FAILED`
olur. RUNNING için `completed_at=NULL`, terminal durumda bitiş tarihi zorunludur
ve başlangıçtan önce olamaz. RUNNING kaydının sonuç alanları güncellenebilir;
identity/start/creation alanları değiştirilemez. Terminal kayıtların UPDATE'i ve
run DELETE'i database integrity trigger'ıyla reddedilir. Düzeltme/yeni inceleme
yeni run'dır; retry/scheduling mekanizması yoktur. `confidence` nullable kısa
protocol etiketi olarak saklanır; ortak score/enum veya güven hesaplaması tanımlamaz.
Run eklemek ya da tamamlamak **IntelligenceState'i otomatik güncellemez**.

`ResearchArtifact`: içerik database'e kopyalanmaz; ayrıntılı Markdown ve kaynaklar
research folder'da kalır. `path` için repository köküne göre `/` ayrımlı göreli
referans kullanılır (ör. `research/UBER/2026-09-14-pass-3/research-report.md`).
OS drive/user yolu saklamak gerekmez. Bu model dosya açmaz, varlık kontrolü yapmaz;
version'lı dosyaların korunması caller'ın sorumluluğudur. `protocol_run_id`
opsiyoneldir. SQL'deki `metadata` kolonunun Python attribute'u, SQLAlchemy'nin
ayrılmış ismiyle çakışmamak için `artifact_metadata`'dır.
Instrument-level run'a bağlanan artifact aynı instrument'a ait olmalıdır;
database trigger'ı INSERT/UPDATE sırasında bu kuralı korur. Portfolio-level run
(`instrument_id=NULL`) farklı instrument artifact'larına sahip olabilir.
Artifact'ın `protocol_run_id=NULL` olması da geçerlidir.

`TechnicalPlan`: yeni analiz için yeni satır oluşturulur; eskisi `active=False`
olarak tutulur. Varsayılan inactive'dir. `WHERE active` partial unique index,
instrument başına **en fazla bir** active planı database seviyesinde korur;
hiç active plan olmaması geçerlidir. Plan DELETE'i reddedilir. Yeni planı
aktive ederken aynı transaction içinde önce eski planı deaktive edip `flush()`,
sonra yeniyi aktive et; otomatik supersede servisi yoktur. Plan içerikleri için
terminal-run benzeri UPDATE kilidi yoktur; eski analiz yeni sonuçla overwrite
edilmemelidir. Reference price `Numeric(28,12)`/Decimal ile tutulur ve instrument'ın
currency'siyle yorumlanır. TechnicalPlan–ProtocolRun arasında zorunlu ilişki yoktur.
Activation/switch **atomic transaction** içinde yapılmalıdır; ara commit yapılmaz.
Activation başarısızsa tüm transaction rollback edilerek eski active plan korunur.
Concurrent activation'da unique index ikinci işlemi bekletebilir/reddedebilir;
başarısız işlem rollback edilmelidir. İki bağımsız connection ile bu davranış test edilir.

History foreign key'leri `RESTRICT` kullanır; bağlı history varken instrument
silinemez, ORM de bağlantıları otomatik NULL'a çevirmez. Artifact–run bağlantısı
silme sırasında korunur. Bu korumalar normal row UPDATE/DELETE içindir; database
sahibinin schema/truncate işlemleri için bir yetkilendirme sistemi değildir.

Machine record, artifact metadata ve zone'lar **JSONB**'dir: protocol-specific
structured data için ayrı tablolar gerektirmez. Python `None` SQL NULL olur;
exact JSON schema validation sonraki katmana aittir. SQLAlchemy'de JSON değişimi
için yeni dict/list atayın; nested in-place mutation otomatik izlenmez.

## Migration

`0001` ve `0002` değişmeden korunur; `alembic upgrade head` sırasıyla
`0001 → 0002 → 0003` uygular. `0003`, Part 2 artifact/run consistency düzeltmesidir;
Part 3 modelleri içermez. Mevcut uyumsuz artifact/run eşleşmesi varsa upgrade
başarısız olur; history otomatik değiştirilmez. Attribution düzeltilip tekrar
upgrade edilmelidir. `0003 → 0002` downgrade yalnız bu yeni guard'ı kaldırır,
verileri korur.
`0002` üç history tablosu, run-status enum, index'ler ve integrity guard'larını
ekler. `alembic downgrade 0001` yalnız Part 2 yapılarını ve verilerini kaldırır;
Part 1 instrument/current-state verisini korur. Tam downgrade test database'inde
`base` hedefiyle doğrulanır. Schema için Alembic kullanılması integrity trigger'ları
da kurar; `create_all()` onların yerini tutmaz.

## Local development (PowerShell, repository kökünden)

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e '.[test]'

$env:II_DB_HOST = '127.0.0.1'
$env:II_DB_PORT = '55432'
$env:II_DB_NAME = 'investment_intelligence'
$env:II_DB_USER = 'ii_local'
$secret = Read-Host 'Local PostgreSQL password' -AsSecureString
$env:II_DB_PASSWORD = [System.Net.NetworkCredential]::new('', $secret).Password

docker compose -p investment-intelligence up -d --wait
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic current
```

Host/port defaults `127.0.0.1:55432`; name/user/password zorunlu environment
variables'dır. `.env.example` yalnız Compose için örnektir; `.env` gitignore'dadır.
Python `.env` dosyasını otomatik okumaz, yukarıdaki process environment'ı okur.
URL, özel karakterli parolaları elle escape etmeden SQLAlchemy `URL.create` ile
kurulur. Import sırasında database bağlantısı açılmaz.

Compose ayrı PostgreSQL 17 container'ı ve kalıcı volume oluşturur; port yalnız
localhost'a açılır. İlk initialization sonrası password/name/user değiştirmek
mevcut volume'deki kullanıcı/database'i değiştirmez. Local user container'ın
initialization yöneticisidir; production role tasarımı bu part'ın kapsamında değildir.

Uygulama kodunda `create_db_engine()` ile engine, `sqlalchemy.orm.Session(engine)`
ile session oluşturulur; modeller `investment_intelligence.models` içindedir.
Schema kurmak için `Base.metadata.create_all()` yerine Alembic kullanılır.

## Testler

Config testleri PostgreSQL gerektirmez:

```powershell
.venv/Scripts/python.exe -m pytest -m 'not postgres' -q
```

Tam test suite için yukarıdaki **ayrı local PostgreSQL server** üzerinde `CREATEDB`
yetkili bağlantıyı belirt:

```powershell
$env:II_TEST_ADMIN_URL = (.venv/Scripts/python.exe -c 'from investment_intelligence.database import database_url; print(database_url().render_as_string(hide_password=False))')
.venv/Scripts/python.exe -m pytest -q
Remove-Item Env:II_TEST_ADMIN_URL
```

Test URL'sini konsola/log'a yazma. Testler verilen URL'deki database'i migrate/drop
etmez: rastgele `ii_test_<uuid>` database oluşturur, migration'ı uygular ve sonunda
yalnız bu test database'ini siler. NetWorth veya production bağlantısı kullanma.
Test environment eksikse integration testleri skip yerine fail olur.

Kapsam: create/read, nullable state, enum roundtrip ve geçersiz değerlerin ORM/DB
tarafından reddi, one-to-one/FK, delete cascade, update timestamp, fresh migration,
downgrade/upgrade ve model–migration schema uyumu. Ek olarak UTC/offset roundtrip,
naive datetime reddi, ayrı connection'lar arasında gerçek commit/rollback,
loaded/unloaded ORM delete ve aynı symbol'ün farklı venue/type'larda saklanması.
Part 2 testleri generic/portfolio-level run, terminal history immutability,
JSONB/nullable alanlar, artifact ilişkileri, technical plan history/tek active plan,
history FK/delete koruması, yeni alanlarda UTC contract ve veri içeren Part 1
database'inin `0002` upgrade'ini kapsar.
Ek testler artifact/run consistency (INSERT/UPDATE), concurrent activation,
başarısız switch sonrası tam rollback, JSONB replacement persistence ve terminal
Machine Record UPDATE reddini doğrular. JSONB için yeni dict/list assignment
kullanılır; nested in-place mutation tracking eklenmemiştir.

Local server'ı durdurmak için `docker compose -p investment-intelligence stop`.
Volume ve geliştirme verileri korunur.

## Repository ve Service Katmanı — MVP Part 3

Gelecekteki Context Builder ve Protocol Runner'ın doğrudan ORM/SQL query detaylarıyla uğraşmaması için sade, application-facing bir persistence API'si sunulmuştur (`investment_intelligence.repositories`, `investment_intelligence.services` ve `investment_intelligence.records`).

### Amacı ve Sınırları
- Direct ORM bağımlılığı yerine dondurulmuş (frozen dataclass) snapshot record'lar (`InstrumentRecord`, `IntelligenceStateRecord`, `ProtocolRunRecord`, `ResearchArtifactRecord`, `TechnicalPlanRecord`) döner. JSONB alanları `deepcopy` ile izole edilmiştir.
- Event bus, UnitOfWork, generic repository veya DI framework eklenmemiştir; sade SQLAlchemy Session injection kullanılır.

### Transaction Ownership
- Transaction boundaries tamamen **caller** mülkiyetindedir (`with session.begin(): ...`).
- Repository ve service metotları asla doğrudan top-level `commit()` veya `rollback()` çağırmaz; yarım commit bırakmaz.
- Write işlemleri `with session.begin_nested():` (savepoint) içinde çalışır; bir yazma hatası oluşursa yalnız o savepoint geri alınır, caller'ın transaction bütünlüğü korunur.
- Session temizliği denetlenir; un-flushed ORM objesi olan veya aborted transaction durumundaki session'lar erken reddedilir.

### Current State ile History Ayrımı
- `IntelligenceStateRepository`, instrument'ın güncel state'ini (`thesis`, `valuation`, `technical`, `recommendation`, monitoring timestamps) yönetir. State alanları nullable kalabilir.
- `ProtocolRunService` (execution history) ve `ResearchArtifactRepository` (evidence references) history kayıtlarını tutar.
- Bir protocol run'ı başlatmak veya tamamlamak IntelligenceState'i **otomatik güncellemez**; state güncellemesi açık bir application kararıdır.
- Terminal protocol run'lar (`COMPLETED`, `FAILED`) değiştirilemez (immutable).

### TechnicalPlan Activation Semantics
- `TechnicalPlanService.create_inactive(...)`: Her yeni analiz yeni bir plan satırı olarak (`active=False`) oluşturulur; eski analiz satırları üzerine yazılmaz (history korunur).
- `activate_technical_plan(plan_id)`: Atomik olarak mevcut active planı `active=False`, hedef planı `active=True` yapar.
- Başarısızlık durumunda (veya transaction rollback'inde) savepoint geri alınır ve önceki aktif plan aktif kalmaya devam eder.
- PostgreSQL partial unique index (`uq_technical_plans_active_instrument`) sayesinde eşzamanlı çakışmalar `TechnicalPlanActivationConflictError` olarak yakalanır.

### Gelecek Kullanım
- Gelecekteki **Context Builder**, compact LLM context'i derlemek için bu katmandaki `get`, `list`, `get_active_technical_plan` ve `recent` gibi okuma API'lerini kullanacaktır.
- Gelecekteki **Protocol Runner**, protokol yaşam döngüsünü yönetmek için `ProtocolRunService.start/complete/fail` operasyonlarını çağıracaktır.
