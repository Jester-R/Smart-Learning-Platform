# All-in-One Student Portal — Cambodia

This repository is the Smart Learning Platform LMS foundation for the planned All-in-One
Student Portal. It currently includes the working academic LMS described below; the target
scope, role permissions, and expanded database design are documented in `docs/`.

## Features

- Custom email-based accounts with administrator, teacher, and student roles.
- Role-based dashboards and navigation.
- Course categories, course management, publishing, thumbnails, and enrollment.
- Lessons with video URLs/files, reading content, ordering, and completion tracking.
- Learning materials (PDF, documents, presentations, video, audio, external links).
- Assignments with attachments, deadlines, late-submission rules, resubmission,
  submissions, grading, and feedback.
- Quizzes and midterm examinations with multiple-choice, true/false, short-answer, and
  essay questions; time limits, attempts, shuffling, automatic grading, manual essay
  grading, and configurable result release.
- Notifications and announcements with audience targeting and delivery.
- Gemini-powered study assistant with role-aware prompts, conversation history, rate
  limiting, and an assessment lockout for students taking a quiz or exam.
- Course completion certificates with PDF generation and public verification.
- Reports and analytics with enrollment and grade charts plus an activity log.
- Django admin for every entity.
- JWT-authenticated REST API.

## Prerequisites

- Windows with PowerShell.
- Python 3.12 (the project uses `.venv`).
- XAMPP with **MySQL/MariaDB running** (Apache is only needed for phpMyAdmin).
- Internet access for the Bootstrap CDN and the Gemini API.

MariaDB 10.4.32 is bundled with this XAMPP installation. Django 5.2 normally requires
MariaDB 10.5+, so the project uses `config.db_backends.mysql`, which lowers the version
check and disables `INSERT ... RETURNING` (unsupported on 10.4). If MariaDB is upgraded
to 10.5 or newer, change `DATABASES` in `config/settings.py` back to
`django.db.backends.mysql` and delete `config/db_backends`.

## Setup

1. Start MySQL from the XAMPP Control Panel (or run `C:\xampp\mysql_start.bat`).

2. Create the database (safe to run again):

   ```powershell
   & 'C:\xampp\mysql\bin\mysql.exe' -u root -e "CREATE DATABASE IF NOT EXISTS smart_learning CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
   ```

3. Activate the virtual environment and install dependencies:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

4. Create `.env` from `.env.example` if it does not exist, then set `DJANGO_ENV`
   (`development` or `production`), `DJANGO_SECRET_KEY`, the database credentials,
   and `GEMINI_API_KEY`. Never commit `.env`.

5. Apply migrations and seed the RBAC data:

   ```powershell
   python manage.py migrate
   python manage.py seed_roles
   python manage.py seed_phase4
   ```

6. Run the checks and tests:

   ```powershell
   python manage.py check
   python manage.py test
   ```

7. Run the development server:

   ```powershell
   python manage.py runserver
   ```

   Open <http://127.0.0.1:8000/>. The public landing page reports the live database
   connection. Sign in to reach the role dashboard.

## Development accounts

These accounts were created for local development. Change or remove them before any real
deployment.

| Role | Email | Password |
| --- | --- | --- |
| Administrator | `admin@smartlearning.local` | `Admin@12345` |
| Teacher | `teacher@smartlearning.local` | `Teacher@12345` |
| Student | `student@smartlearning.local` | `Student@12345` |

The administrator dashboard can be filled with demo data at any time:

```powershell
python manage.py seed_dashboard_data
```

The command is safe to run repeatedly and tops the platform up to 920 students, 96
teachers, 89 courses, 6 announcements, 43 notifications, and 560 certificates. Every
student is enrolled in five courses. It also gives every course an assignment with a mix
of submitted, graded, and returned student work so the teacher dashboard's "Recent
submissions" panel stays populated, and seeds ten weekday attendance records per
enrollment for the student attendance report.
Generated student accounts use the `student0001@smartlearning.local` format with password
`Student@12345`; generated teacher accounts use `teacher0001@smartlearning.local` with
password `Teacher@12345`. Change or remove these accounts before any real deployment.

Demo content includes the published course `WEB101 - Introduction to Web Development`
with two lessons, an assignment, a quiz, and a midterm examination. The development
student is enrolled in the course.

The Django admin is at <http://127.0.0.1:8000/admin/>.

## Main routes

| Area | Route |
| --- | --- |
| Landing page | `/` |
| Dashboard | `/dashboard/` |
| Login / registration | `/accounts/login/`, `/accounts/register/` |
| Courses | `/courses/` |
| Academic timetable, calendar, exams | `/academic/timetable/`, `/academic/calendar/`, `/academic/exam-schedule/` |
| Attendance and attendance recording | `/learning/attendance/`, `/learning/attendance/record/` |
| Notifications and announcements | `/notifications/` |
| AI assistant | `/assistant/` |
| Certificates and verification | `/certificates/`, `/certificates/verify/` |
| Reports (teacher/admin) | `/reports/reports/` |
| Jobs and company hiring | `/careers/`, `/careers/companies/jobs/` |
| Scholarships | `/scholarships/` |
| Community forum and moderation | `/community/`, `/community/moderation/` |
| Events and workshops | `/events/` |
| Help center and support tickets | `/support/`, `/support/tickets/` |
| REST API | `/api/` |
| API token | `/api/auth/token/` |

## REST API

Obtain a JWT with the email/password credentials:

```powershell
$body = @{ email = 'admin@smartlearning.local'; password = 'Admin@12345' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/token/ -ContentType 'application/json' -Body $body
```

Send the access token as `Authorization: Bearer <token>`. Read-only resources:
`courses`, `lessons`, `materials`, `assignments`, `quizzes`, `certificates`. Student
write resources: `enrollments`, `submissions`, and `quizzes/{id}/start/`. Results are
filtered by role and enrollment.

## Project layout

```text
Smart Learning Platform/
├── .env                     # Local secrets (not committed)
├── .env.example
├── .gitignore
├── manage.py
├── requirements.txt
├── README.md
├── config/
│   ├── settings.py           # Environment selector
│   ├── settings_base.py      # Shared settings
│   ├── settings_development.py
│   ├── settings_production.py
│   ├── urls.py
│   ├── views.py             # Landing page with database status
│   ├── db_backends/mysql/   # MariaDB 10.4 compatibility backend
│   └── wsgi.py / asgi.py
├── apps/
│   ├── core/                # Roles, permissions, organizations, auth tokens, RBAC
│   ├── academic/            # Timetables, class sessions, calendars, exam schedules
│   ├── accounts/            # Users, profiles, auth, dashboards, permissions
│   ├── courses/             # Categories, courses, enrollment
│   ├── learning/            # Lessons, materials, progress
│   ├── assessments/         # Assignments, quizzes, exams, grades
│   ├── notifications/       # Announcements and per-user notifications
│   ├── ai_assistant/        # Gemini conversations and messages
│   ├── certificates/        # Certificate issuance, PDFs, verification
│   ├── analytics/           # Reports, activity log, grade audit log
│   ├── careers/             # Company profiles, job packages, jobs, applications
│   ├── scholarships/        # Scholarship categories, listings, applications
│   ├── community/           # Forum posts, comments, likes, saves, reports
│   ├── events/              # Event categories, events, registrations
│   ├── support/             # FAQs, support tickets, feedback
│   └── api/                 # DRF serializers, viewsets, JWT routes
├── templates/               # Reusable Django templates
├── static/                  # Project-wide CSS/JS
├── media/                   # Uploaded and generated files (not committed)
└── docs/
    ├── ERD.md               # Current and target entity relationship diagram
    ├── ROLE_MATRIX.md       # Role and permission authorization matrix
    └── SCOPE.md             # Confirmed product scope and phase gates
```

## Planning documents

- `docs/SCOPE.md` — confirmed product scope, business rules, phase gates, and acceptance criteria.
- `docs/ROLE_MATRIX.md` — roles, permissions, membership entitlements, and enforcement rules.
- `docs/ERD.md` — existing and target database schema integrity rules.

## Troubleshooting

- **`NotSupportedError: MariaDB 10.5 or later is required`** — confirm
  `DATABASES["default"]["ENGINE"]` is `config.db_backends.mysql`.
- **`Can't connect to MySQL server`** — start MySQL in XAMPP and confirm port 3306
  is listening.
- **`Access denied for user 'root'`** — set `DB_USER`/`DB_PASSWORD` in `.env` to the
  credentials configured in phpMyAdmin.
- **`DisallowedHost`** — add the host to `DJANGO_ALLOWED_HOSTS` in `.env`.
- **AI assistant returns a configuration error** — verify `GEMINI_API_KEY` and
  `GEMINI_MODEL` in `.env`, then restart the server.
- **Static files look unstyled** — check internet access to the Bootstrap CDN or
  replace the CDN links in `templates/base.html` with local Bootstrap files.

## Deployment (AWS)

The production instance (`smart-learning.duckdns.org`) runs behind nginx with
Let's Encrypt SSL, gunicorn on `127.0.0.1:8001`, and MySQL/MariaDB.

Pushing to `main` on GitHub is enough: the `smartlearning-autopull.timer`
systemd timer pulls commits every 2 minutes, installs requirements, runs
migrations and `collectstatic`, then restarts `smart-learning.service`.
