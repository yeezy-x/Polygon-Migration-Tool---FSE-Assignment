# Issues Analysis

> **Instructions**: Document the three highest-priority product issues and the three highest-priority code issues. Rank the issues within each category from highest to lowest priority.
> Replace the example entries with your actual findings and explain why each issue deserves its priority. Complete all four questions in the Edge Case Analysis section.
> Rename this file to `ISSUES.md` before submitting.

## Summary

| Type           | Critical | High | Medium | Low | Total |
| -------------- | -------- | ---- | ------ | --- | ----- |
| Product Issues | 0        | 2    | 1      | 0   | 3     |
| Code Issues    | 1        | 1    | 1      | 0   | 3     |

---

## Product Issues

> Product issues are user-facing problems: broken functionality, missing validation, poor UX, data integrity risks visible to users.

### [P1] Users can fetch a problem using only Problem ID

**Severity**: Medium (As the number of problems grow.)

**Location**: 

1. problems/templates/problems/index.html` - Contains the current problem ID input and Fetch Problem button.

2. problems/views.py` - Handles the submitted problem ID and looks up existing problems.

**Description**:  
As the number of problems grow in number it becomes difficult to remember ID for each problem . So we can introduce a way to search a problem by its name, ID , tag , difficulty. 

**Impact** - Finding previously processed problems becomes increasingly inconvenient as the number of problems grows. It also makes repeated operations slower.

**Expected benefit -** Faster problem discovery, easier navigation, and less dependence on manually remembering IDs.

### Suggested Fix

Introduce a **Problem Discovery** section with multiple ways to find previously migrated problems.

1. **Search by name or ID:** Allow users to search using the problem title or Polygon ID.
2. **Difficulty filters:** Filter problems by Easy, Medium, and Hard.
3. **Topic filters:** Filter by existing problem tags.
4. **Recently accessed problems:** Display recently fetched or migrated problems.
5. **Quick access:** Allow users to select an existing problem and reopen its details without manually entering its ID.

---

### [P2] User does not know what is happening when fetching problem data

**Severity**: High

**Location**: `problems/templates/problems/index.html` , `problems/views.py` , `problems/polygon_api.py`

**Description**:  
When user fetches a problem it may take several minutes so currently the interface is displaying a overlay, so the user only sees the overlay and cannot see whats happening. 

**Impact**:

1. Users may think application is stuck or failing somewhere.
2. They cannot identify which operation is taking time.

**Suggested Fix**: Implement background processing using Background jobs or Django background tasks.

---

### [P3] Migaration to azure can overwrite existing files without user confirmation.

**Severity**: High

**Location**: `problems/storage/azure.py` -`delete_problem_files()` and `upload_test_case()`. 

 `problems/polygon_api.py` - 

**Description**:  
When a user initiates azure migration , the application existing blobs unders storage gets overwritten by new test cases. User is not warned. If a upload fails after deletion, the previous files cannot be restored even after using a PostgrSQL transaction. 

**Impact**:

1. Users may overwrite existing test-case files and a failed migration can leave incomplete data.

**Suggested Fix**:  
Display a alert box or confirmation dialog before migrating. Create a temporary backup of old files so that even if migration fails we can recover old data.

---

---

## Code Issues

> Code issues are technical problems: bugs, security vulnerabilities, performance problems, code quality concerns, architectural issues.

### [C1] Inconsistent source of truth for test-case data

**Severity**: High

**Location**: `problems/polygon_api.py` - `get_all_test_cases()` , `get_test_cases_from_redis()` , `store_test_cases_in_redis()`

**Description**: The application handles test cases data through multiple storgae systems - Polygon API, Redis, PostgreSQL, Azure Blob Storage

When migrating test cases to Azure, `migrate_to_azure_blob()` retrieves test cases from Redis rather than PostgreSQL.

This means that even when test cases have already been migrated to the database, the Azure migration still depends on the Redis cache or has to fetch the data again from Polygon.

**Impact**:

- Redis becomes more than just a performance cache; it influences the data used by migration operations.
- Different storage systems can contain different versions of the same test-case data.
- Azure migration may unnecessarily depend on Polygon API availability when the cache is missing.

**Suggested Fix**:
Establish a clear source of truth for complete test-case data.

- Fetch complete test cases from Polygon.
- Use Redis only as a temporary cache to reduce repeated Polygon API requests.

---

### [C2] Azure testcases silently suppresses storgae operation failure.

**Severity**: Medium

**Location**: `problems/AzureTestcase.py`

`upload_test_case()` - Catches exceptions and logs them without re-raising.

`empty_blob()` - catches exceptions and logs them without re-raising.

**Description**: Both functions catch exceptions but do not propagate them to the calling code. So if a n upload fails, the caller cannot determine the failure through an exception. 

**Impact**:  
Failed uploads can go unnoticed if the user relies on exceptions to detect failures.

Debugging storage related problems can become harder.

**Suggested Fix**: Allow exceptions to propagate after logging them:

---

### [C3]Azure migration can permanently delete existing data when an upload fails

**Severity**: Critical

**Location**: `problems/storage/azure.py` - Deletes all existing blobs for a problem.

**Description**: The application deletes the existing test cases before confirming that the replacement files can be uploaded successfully. 

**Impact**:

- Existing working test-case files can be permanently lost.
- Failed migrations can leave Azure with incomplete data.
- PostgreSQL transactions cannot roll back Azure Blob Storage operations.

**Suggested Fix**: Implement a safer staged migration

- Upload new test cases to a temporary place. Validate that there is no missing in input and output test cases. 
- Verify all files were uploaded successfully and only upon successful verifcation upload new files.

---

---

## Edge Case Analysis

### Q1

> A Polygon problem has 0 sample test cases but 15 regular test cases. What happens when you migrate this problem?

A problem record is created in PostgreSQL but during this the backend filters the fetched test cases using (is_sample) and those marked as sample tests are pushed into SampleTestCase table. 

So if it has 0 sample test case then no SampleTestCase record created. and to save those regular test case user must seperately click Migrate Test Description to Database. 

---

### Q2

> A problem is migrated with 20 test cases. Later, the problem setter removes 8 test cases on Polygon (now 12 remain). The problem is re-migrated. What happens?

The application updates existing `ProblemTestCase` records based on their `order` value. The backend fetches the latest 12 test cases from polygon. 

Inside database still the 20 exists even though ploygon has only 12. So remigration updates existing records but does not enforce deletion.

---

### Q3

> Two different Polygon problems have the exact same title: "Two Sum". You migrate the first one successfully. Then you try to migrate the second one. What happens?

An error occurs - Uniquesness constraint violation. 

Since Problem model enforces uniquesness on slug field. So error occurs when application attempts to create the second problem with same name. So the operation is rolled back. 

To improve this we can generate unique slugs by combining title and problem id. So different problems can have same title yet differs by slug. 

---

### Q4

> When test cases are saved to the database via "Migrate Test Cases to DB", some data is intentionally discarded. What data is lost? Why might this cause problems?

During database migration the application truncates input and output before saving to PostgreSQL. 

Only the first 260 characters of each test input are stored and the first 260 characters of each expected output are stored. Any remaining characters are permanently discarded from those database records. The test description, `is_sample`, and `order` are retained.

What data is lost? - Tests containing more than 260 characters become incomplete.

What problem is caused.? - The database no longer contains a complete representation of the original Polygon test cases.

---

## Severity Guidelines

Use these definitions when assigning severity:

| Severity | Definition | Examples |
|----------|------------|----------|
| **Critical** | System broken, security vulnerability, data loss | SQL injection, authentication bypass, data corruption |
| **High** | Major functionality broken, significant data integrity risk | Feature doesn't work, orphaned records, race conditions |
| **Medium** | Feature partially broken, poor UX, code maintainability | Missing validation, confusing errors, code duplication |
| **Low** | Minor issues, cosmetic, best practice violations | Unused imports, inconsistent formatting, missing logs |

---
