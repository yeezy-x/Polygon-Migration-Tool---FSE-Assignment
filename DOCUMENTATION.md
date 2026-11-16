# **PolygonMigration**

## **2.1 User Flows**

### **Flow 1 - User login**

**1. What the user clicks or submits**

The user opens [http://localhost:8000/users/login/](http://localhost:8000/users/login/), which renders users/templates/users/login.html through login_view in users/[views.py](http://views.py). The page has a form which has Email and Password fields. The user clicks the Login button and the problem migrator page opens.

**2. What the frontend sends**

The form is method="post" and includes Django’s CSRF token.

| **Field**           | **Source**       |
| ------------------- | ---------------- |
| email               | Email input      |
| password            | Password input   |
| csrfmiddlewaretoken | {% csrf_token %} |

**3. What the backend does, in order**

login_view (users/[views.py](http://views.py)):

1. If [request.user.is](http://request.user.is)_authenticated, it calls logout(request) and clears the current session before continuing.
2. On POST, it reads email and password from [request.POST](http://request.POST).
3. It calls authenticate(request, username=email, email=email, password=password).
4. AUTHENTICATION_BACKENDS in PolygonMigration/[settings.py](http://settings.py) tries users.backends.EmailBackend first. EmailBackend.authenticate loads User with User.objects.get(email=email), then returns the user only when user.check_password(password) succeeds and user_can_authenticate allows the account (is_active is true). A missing user or a bad password returns None.
5. If authentication returns a user and [user.is](http://user.is)_staff is true, the view calls login(request, user), which stores the user id in the session.
6. It redirects to the URL named problems:index, which is /.
7. A failed password check adds the message Invalid email or password. A successful password check for a non-staff user adds You do not have staff access. In both cases the login template is rendered again and the messages framework prints the alert.

**4. External APIs**

None.

**5. What is read or written**

- **Read:** users_user, looked up by email. The password is checked against the stored hash. is_active and is_staff are read.
- **Write:** no user row is created or updated. A successful staff login creates or updates a django_session row. The browser receives the sessionid cookie. SESSION_COOKIE_AGE is 86400 seconds (one day).

**6. What the user sees**

| **Outcome**                         | **Page**                                                                                                                          |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Staff user, correct password        | Redirect to /, the problem migrator (problems/templates/problems/index.html). The navbar shows Welcome, {first_name} {last_name}. |
| Unknown email or wrong password     | Login page with Invalid email or password.                                                                                        |
| Correct password, is_staff is false | Login page with You do not have staff access.                                                                                     |

### **Flow 2 - Fetching a problem from Polygon**

**1. What the user clicks or submits**

On /, the user types a Polygon problem id into the input named problem_id and clicks **Fetch Problem** (#fetchForm in problems/templates/problems/index.html). The page script shows a full-screen overlay: Fetching problem data and test cases (may take 3-4 minutes)..., then submits the form.

**2. What the frontend sends**

POST / with:

| **Field**           | **Value**              |
| ------------------- | ---------------------- |
| csrfmiddlewaretoken | CSRF token             |
| problem_id          | The Polygon problem id |
| session cookie      | The staff session      |

migrate_to_db, migrate_test_cases_to_db, and migrate_to_azure are absent, so index treats the request as a fetch.

**3. What the backend does, in order**

Inside `index()` (`problems/views.py`):

1. Loads all `ProblemTag` records for the tag picker and reads the submitted problem ID and migration flags.
2. Initializes `PolygonAPI` using the configured API credentials.
3. Checks whether the problem already exists in PostgreSQL. If it does, loads its saved difficulty and tags and fetches its main solution from Polygon.
4. Starts a database transaction. Since this is a normal fetch, all migration and database-write branches are skipped.
5. Calls `problem.info` to retrieve problem details.
6. Downloads the latest standard problem package using `problem.packages` and `problem.package`, extracts `problem.html`, and parses the title, statement, input format, output format, and notes.
7. Fetches all test cases using `problem.tests`, `problem.testInput`, and `problem.testAnswer`, then caches them in Redis for 30 minutes.
8. Retrieves the checker using `problem.checker`, identifies supported checker types, and detects custom checkers when applicable.
9. Calls `problem.tests` again to determine the total test-case count.
10. Builds the problem details and test-case previews, then renders `problems/index.html`.

No PostgreSQL records are created or updated during a normal fetch.

**4. External APIs**

Polygon, all POST to [https://polygon.codeforces.com/api/{method}](https://polygon.codeforces.com/api/{method}):

| **Method**                                    | **Called from**                                                 | **Purpose**                                             |
| --------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------- |
| [problem.info](http://problem.info)           | get_problem_info, and again inside download_and_extract_package | Name, timeLimit, memoryLimit                            |
| problem.packages                              | download_and_extract_package                                    | List packages; the latest standard package is chosen    |
| problem.package                               | download_and_extract_package                                    | Download that package as a zip                          |
| problem.tests                                 | get_all_test_cases and get_test_cases                           | Test index, description, useInStatements                |
| problem.testInput                             | get_all_test_cases                                              | Plain-text input for one test                           |
| problem.testAnswer                            | get_all_test_cases                                              | Plain-text answer for one test                          |
| problem.checker                               | index and get_custom_checker_info                               | Checker name                                            |
| problem.updateWorkingCopy                     | index, only when a Problem row already exists                   | Refresh Polygon’s working copy before reading solutions |
| [problem.solutions](http://problem.solutions) | same branch                                                     | Solution list                                           |
| problem.viewSolution                          | same branch                                                     | Source of the main solution                             |

Redis is used as a cache, not as the system of record. See the write below.

**5. What is read or written**

- **PostgreSQL read:** all problems_problemtag rows. One problems_problem lookup by polygon_id. If the row exists, its problems_problem_extra_tags links are read.
- **PostgreSQL write:** none for a fetch.
- **Redis write:** store_test_cases_in_redis sets polygon_migration_test_cases_{polygon_id}_count and polygon_migration_test_cases_{polygon_id}_test_{n} for each test, with a 30-minute TTL (expiry_hours=0.5). Each test value is JSON with index, input, output, description, and is_sample. Connection settings are REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, and REDIS_SSL.
- **Local disk:** the package zip exists only inside a temporary directory, which download_and_extract_package removes before returning.

**6. What the user sees**

The overlay goes away and the same page shows **Fetched Problem: {title} (Polygon ID: {id})**. The table includes slug, difficulty (empty until a problem is saved), tags, time limit, memory limit, checker type, custom-checker name when one exists, and test-case count. Statement, input format, output format, and notes are rendered from the parsed HTML. A table lists every test with a short preview and a View Full button. **Create/Update problem in Database** is enabled. **Migrate Test Cases to Azure** and **Migrate Test Description to Database** stay disabled until a Problem row exists. The main-solution block shows the solution source only when the problem was already in the database; otherwise it shows Please migrate the problem to the database first.

A Polygon or parse failure renders a red alert: Migration failed and all changes have been rolled back. Reason: ….

### **Migrating a problem to the database**

**1. What the user clicks or submits**

After a problem has been fetched, the user picks Easy, Medium, or Hard in #difficulty-select and optionally searches or adds tags. They click **Create/Update problem in Database** (#migrate-db-form). The submit handler refuses an empty difficulty with Please select a difficulty level before submitting. Otherwise it copies the selected tag names into hidden tags inputs, shows Migrating to database..., and posts the form.

**2. What the frontend sends**

POST / with:

| **Field**           | **Value**                                                           |
| ------------------- | ------------------------------------------------------------------- |
| csrfmiddlewaretoken | CSRF token                                                          |
| problem_id          | Polygon id kept in a hidden input                                   |
| migrate_to_db       | 1                                                                   |
| difficulty          | easy, medium, or hard                                               |
| tags                | Repeated once per selected tag, including a tag the user just typed |

index also reads new_tag when that field is posted. The current template puts newly typed tags into the tags list in updateHiddenInputs() and does not add a separate new_tag input.

**3. What the backend does, in order**

The request still enters index and runs the same Polygon fetch described above, with two differences before the write: the migration flags are set, and test cases are taken from Redis when get_test_cases_from_redis finds them. On a cache miss it calls get_all_test_cases and stores the result for 30 minutes.

The database write runs only when migrate_to_db is set, inside transaction.atomic():

1. If difficulty is empty, the view raises Please select a difficulty level before migrating to database. The atomic block rolls back.
2. It loads Problem by polygon_id.
3. If the row exists, it updates title, slug (slugify of the title), difficulty, problem_statement, input_format, output_format, constraints (empty string), editorial (empty string), time_limit, memory_limit, checker_type, test_case_count, polygon_id, and notes, then save().
4. If the row does not exist, it creates a Problem with those fields. Other model fields keep their defaults (avg_time_taken=30.0, total_submissions=0, is_locked=False, genie_assist=False, genie_plus=False, genie_chat=False).
5. It clears problem_obj.extra_tags, then get_or_creates a ProblemTag for each posted tag name and for new_tag when that value is non-empty, and adds each tag to the problem.
6. It reads test cases from Redis, or from Polygon on a cache miss.
7. It keeps the tests whose is_sample is true. For each sample with both input and output, it strips trailing whitespace and either updates the existing SampleTestCase at that position or creates one. order starts at 1. Sample text is stored in full. Sample rows beyond the new list are left in place.
8. It reloads the Problem into db_problem.
9. It calls [problem.solutions](http://problem.solutions) and problem.viewSolution again and puts the main solution on the page. This second fetch does not call problem.updateWorkingCopy (that call happens only in the earlier “already in the database” branch).

**4. External APIs**

The same Polygon methods as a fetch. Because migrate_to_db is set, get_all_test_cases runs only when the Redis keys for this Polygon id are missing. [problem.solutions](http://problem.solutions) and problem.viewSolution run again at the end of the save. problem.updateWorkingCopy runs only when a Problem row already existed at the start of the request.

**5. What is read or written**

- **PostgreSQL write:** insert or update problems_problem. Replace rows in the problems_problem_extra_tags join table. Insert problems_problemtag when a tag name is new. Insert or update problems_sampletestcase for sample tests that have both input and output.
- **PostgreSQL read:** Problem by polygon_id, existing sample rows ordered by order, and the tags just attached.
- **Redis:** read polygon_migration_test_cases_{polygon_id}_*. Write those keys when the cache is empty.
- **Not written here:** problems_problemtestcase. That table is filled by the next flow. Full test files are not uploaded to cloud storage in this step.

**6. What the user sees**

A blue **Database Operation** alert:

- Problem '{title}' created in database successfully.
- or Problem '{title}' updated in database successfully.

If get_custom_checker_info returned a checker, the sentence Custom checker '{name}' detected. is appended. The page also shows the new database id, an Algopath link [https://www.algopath.ai/problems/{slug}](https://www.algopath.ai/problems/{slug}), the saved difficulty and tags, the statement, and the test-case table. **Migrate Test Cases to Azure** and **Migrate Test Description to Database** become enabled. The main-solution block shows the source returned by problem.viewSolution when Polygon returned one.

Missing difficulty, a Polygon error, or a database error replaces the page with the rollback alert. A duplicate slug raises an integrity error and is rolled back the same way.

### **Migrating test cases to the database**

**1. What the user clicks or submits**

Under the test-case table the user clicks **Migrate Test Description to Database** (#migrate-test-cases-form). The button is disabled, with the tooltip Please migrate the problem to the database first., until db_problem is present. The click shows Migrating test descriptions to database... and submits the form.

**2. What the frontend sends**

POST / with:

| **Field**                | **Value**  |
| ------------------------ | ---------- |
| csrfmiddlewaretoken      | CSRF token |
| problem_id               | Polygon id |
| migrate_test_cases_to_db | 1          |

**3. What the backend does, in order**

index still refreshes the Polygon display data inside transaction.atomic() before it writes test cases. With this flag set, test cases for the display come from Redis when present.

The write itself:

1. Problem.objects.filter(polygon_id=polygon_id).first(). If there is no row, the view raises Please migrate the problem to the database first.
2. get_test_cases_from_redis(polygon_id). On a miss, get_all_test_cases calls Polygon and store_test_cases_in_redis caches the result for 30 minutes.
3. It loads existing ProblemTestCase rows for that problem, ordered by order.
4. For each test that has both input and output, it keeps the first 260 characters of input and of output (input_data[:260], output_data[:260]), copies is_sample and description, and sets order starting at 1. An existing row at that index is updated. Otherwise ProblemTestCase.objects.create inserts one. Tests with empty input or empty output are skipped. Extra ProblemTestCase rows past the new list are not deleted.

SampleTestCase rows are not changed by this button. Those are written while migrating the problem.

**4. External APIs**

The display refresh uses the Polygon methods listed in the fetch flow. The test-case bodies used for the database write come from Redis when polygon_migration_test_cases_{polygon_id}_count is present. On a cache miss the write path calls problem.tests, problem.testInput, and problem.testAnswer.

**5. What is read or written**

- **PostgreSQL read:** problems_problem by polygon_id, then problems_problemtestcase for that problem.
- **PostgreSQL write:** update or insert problems_problemtestcase. Stored input and output are truncated to 260 characters. description, is_sample, and order are stored in full. created_at is set on insert; updated_at changes on save.
- **Redis:** read the Polygon-id cache; write it on a miss.
- **Cloud storage:** unchanged.

**6. What the user sees**

A green **Success** alert: Test cases description migrated to database Successfully. The fetched problem and the test-case preview table are shown again. The previews still use the full Polygon text held in memory for the page; the 260-character limit applies to the database rows.

If the problem has not been saved, the user sees Migration failed and all changes have been rolled back. Reason: Please migrate the problem to the database first.

### **Uploading test cases to cloud storage**

**1. What the user clicks or submits**

The user clicks **Migrate Test Cases to Azure** (#migrate-azure-form). The button is disabled until the problem has a database row. The click shows Migrating to Azure... and submits the form.

**2. What the frontend sends**

POST / with:

| **Field**           | **Value**  |
| ------------------- | ---------- |
| csrfmiddlewaretoken | CSRF token |
| problem_id          | Polygon id |
| migrate_to_azure    | 1          |

**3. What the backend does, in order**

Inside transaction.atomic() in index, the Azure branch runs before the display refresh:

1. Load Problem by polygon_id. If it is missing, set error to Problem with Polygon ID {id} has not been migrated to the database yet. Please migrate the problem to the database first before migrating test cases to Azure. and render the page immediately.
2. Read AZURE_STORAGE_ACCOUNT_URL, AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, and AZURE_CONTAINER_NAME from settings.
3. Use problem_[obj.id](http://obj.id) (the PostgreSQL primary key) as the storage directory name.
4. Call api.delete_problem_test_case_cache(problem_[obj.id](http://obj.id)). That scans Redis for oj_dev_with_redis_storage_test_cases_{db_problem_id}* and deletes matching keys. The cache this app writes uses the polygon_migration_test_cases_ prefix, so this scan does not remove the keys filled by a fetch.
5. Call get_custom_checker_info. If a custom checker exists, the page context gets an info string. The template does not render context['info']; the success message does mention the checker.
6. Call PolygonAPI.migrate_to_azure_blob(...).

migrate_to_azure_blob (problems/polygon_[api.py](http://api.py)):

1. Load test cases from Redis under polygon_migration_test_cases_{polygon_id}_*. On a miss, fetch them from Polygon and cache them for 30 minutes.
2. Call get_storage_provider (problems/storage/[factory.py](http://factory.py)). STORAGE_PROVIDER defaults to azure, which returns AzureStorageProvider.
3. AzureStorageProvider builds a ClientSecretCredential from the tenant id, client id, and client secret, then a BlobServiceClient for AZURE_STORAGE_ACCOUNT_URL.
4. delete_problem_files lists blobs whose names start with test_cases/{db_problem_id}/ and deletes them.
5. For each test that has both input and output, upload_test_case writes the full text, numbered from 1 in list order.
6. upload_custom_checker_to_azure runs. If problem.checker names a file that does not start with std::, it downloads that file with problem.viewFile (first as type=source, then type=resource, then source with .cpp appended). It compiles the source with g++-std=gnu++17 -O2 in CUSTOM_CHECKER_DIR when that setting is set, otherwise in a temporary directory. The binary is uploaded. If compilation fails, the .cpp source is uploaded instead.

After storage returns, index continues with the same display refresh as a fetch ([problem.info](http://problem.info), the package, test cases, problem.checker). A later exception in that refresh rolls back the database transaction. Blob uploads are already complete. The exception handler then calls the undefined api.delete_azure_blob.

**4. External APIs**

- Polygon methods used to obtain tests and checker source, as in the fetch flow, plus problem.viewFile when a custom checker is uploaded.
- Azure Blob Storage. Authentication is a client-secret credential (azure.identity.ClientSecretCredential), and uploads go through [azure.storage](http://azure.storage).blob.BlobServiceClient. Each upload calls upload_blob(..., overwrite=True).
- Redis, for the test-case cache and for the oj_dev_with_redis_storage_test_cases_{id}* delete.

**5. What is read or written**

- **PostgreSQL read:** problems_problem by polygon_id, to obtain the integer primary key and to confirm the problem was migrated. This flow does not insert or update problem or test-case rows.
- **Redis:** read polygon_migration_test_cases_{polygon_id}*; write them on a miss. Delete keys matching oj_dev_with_redis_storage_test_cases*{db_problem_id}.
- **Blob container** (AZURE_CONTAINER_NAME), after the old prefix is removed:

| **Blob name**                                 | **Contents**                                                                                             |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| test_cases/{db_problem_id}/{nn}               | Full input, UTF-8. {nn} is the 1-based position in the test list, zero-padded to two digits (01, 02, …). |
| test_cases/{db_problem_id}/{nn}.a             | Full expected output, UTF-8.                                                                             |
| test_cases/{db_problem_id}/custom_checker     | Compiled checker binary on Linux. On Windows the name is custom_checker.exe.                             |
| test_cases/{db_problem_id}/custom_checker.cpp | Checker source, written when compilation fails.                                                          |

Tests with empty input or empty output are not uploaded. A standard Polygon checker (std::…) produces no checker blob.

**6. What the user sees**

A green **Success** alert: Test cases migrated to Azure Blob Storage successfully. If a custom checker was detected before the upload, the alert continues with Custom checker '{name}' was also compiled and uploaded. The fetched problem and test-case table are rendered again.

If the problem is not in the database, the red alert is the “has not been migrated” message above. An Azure, Polygon, or compile failure surfaces as Migration failed and all changes have been rolled back. Reason: ….

## **2.2 External Integrations**

### **Polygon API**

All Polygon calls are made by PolygonAPI in problems/polygon_[api.py](http://api.py). The base URL is [https://polygon.codeforces.com/api/](https://polygon.codeforces.com/api/). Every call is an HTTP POST with form fields. JSON methods go through *make*request, which returns the result field. A body whose status is FAILED raises Polygon API Error: {comment}. File and test bodies go through *make*plain_request, which returns the response text.

Credentials come from the environment via PolygonMigration/[settings.py](http://settings.py):

- POLYGON_API_KEY is sent as apiKey.
- POLYGON_API_SECRET is used only to build the signature. It is not sent as its own field.

*generate*api_sig authenticates each request:

1. Add apiKey and time (Unix seconds) to the method parameters.
2. Sort the parameters by name and encode them with urllib.parse.urlencode.
3. Build a 6-character prefix from lowercase letters and digits.
4. Hash this string with SHA-512: {prefix}/{methodName}?{encoded_params}#{api_secret}.
5. Set apiSig to {prefix}{hex_digest}.

The posted form contains the method parameters plus apiKey, time, and apiSig.

Endpoints the running flows call:

| **Endpoint**                                  | **Used for**                                                                             |
| --------------------------------------------- | ---------------------------------------------------------------------------------------- |
| [problem.info](http://problem.info)           | Problem name and limits                                                                  |
| problem.packages                              | Available packages                                                                       |
| problem.package                               | Zip download of the latest standard package                                              |
| problem.tests                                 | Test list for the tests testset                                                          |
| problem.testInput                             | One test’s input                                                                         |
| problem.testAnswer                            | One test’s answer                                                                        |
| problem.checker                               | Checker name                                                                             |
| problem.viewFile                              | Custom checker source (type source or resource)                                          |
| problem.updateWorkingCopy                     | Refresh the working copy before reading a solution for a problem already in the database |
| [problem.solutions](http://problem.solutions) | Solution list; the MA tag marks the main solution                                        |
| problem.viewSolution                          | Main solution source                                                                     |

PolygonAPI also defines get_statements (problem.statements), get_test_script (problem.script), get_problem_files (problem.files), and get_file_content (problem.viewFile). The five flows above do not call those methods.

### **Cloud storage**

STORAGE_PROVIDER selects the backend in get_storage_provider (problems/storage/[factory.py](http://factory.py)). The default is azure, which constructs AzureStorageProvider (problems/storage/[azure.py](http://azure.py)). The provider implements StorageProvider (problems/storage/[base.py](http://base.py)): upload_test_case, upload_blob, and delete_problem_files. Any other STORAGE_PROVIDER value raises Unsupported storage provider.

Azure settings, all read from the environment:

| **Setting**               | **Role**                                     |
| ------------------------- | -------------------------------------------- |
| AZURE_STORAGE_ACCOUNT_URL | Blob account URL passed to BlobServiceClient |
| AZURE_TENANT_ID           | Azure AD tenant for ClientSecretCredential   |
| AZURE_CLIENT_ID           | Application (client) id                      |
| AZURE_CLIENT_SECRET       | Client secret                                |
| AZURE_CONTAINER_NAME      | Container that receives every blob           |

The client authenticates as an application with that client secret. upload_blob overwrites an existing blob of the same name.

Files for one problem share the prefix test_cases/{db_problem_id}/, where {db_problem_id} is problems_[problem.id](http://problem.id), not the Polygon id. Before an upload, migrate_to_azure_blob deletes every blob under that prefix, then writes the new set:

- Input for the *n*th uploaded test: test_cases/{db_problem_id}/{nn} with no extension. nn is n formatted as two digits.
- Output for that test: test_cases/{db_problem_id}/{nn}.a.
- Compiled custom checker: test_cases/{db_problem_id}/custom_checker (or custom_checker.exe when the app is running on Windows).
- Checker source, only when g++ fails: test_cases/{db_problem_id}/custom_checker.cpp.

problems/[AzureTestcase.py](http://AzureTestcase.py) - (AzureBlobManager) builds the same test_cases/{id}/{nn} and {nn}.a names. The migration path does not use that class; it uses AzureStorageProvider.
