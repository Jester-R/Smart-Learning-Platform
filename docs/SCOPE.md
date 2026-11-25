# Confirmed Scope — All-in-One Student Portal (Cambodia)

## Product definition

The target product is a professional, responsive, multi-role EdTech portal for university students in Cambodia. It combines academic learning, student services, career opportunities, scholarships, community, events, support, and a hybrid monetization system in one Django application.

The existing repository is a strong LMS foundation and will be extended, not rewritten. Current verified baseline: Django 5.2, DRF, SimpleJWT, MySQL/MariaDB, Bootstrap 5, 160 passing tests, custom email-based user model, role dashboards, courses, lessons, materials, assignments, quizzes, exams, grades, attendance, certificates, notifications, AI assistant, analytics, manual course/subscription payments, refunds, JWT API, RBAC, and academic scheduling.

## Confirmed user roles

| Role | Description |
| --- | --- |
| Guest | Unauthenticated visitor. Can browse public landing page, public course/scholarship/job/event listings, and verification pages. |
| Free Student | Authenticated student on the FREE plan. Accesses essential academic and community features. |
| Student Pro | Authenticated student on the paid PRO tier. Adds ad-free access, premium materials, advanced practice, CV templates, and learning analytics. |
| Student Premium | Authenticated student on the highest tier. Adds premium courses, advanced resources, career materials, exclusive workshops, and priority support. |
| Lecturer / Teacher | Teaches courses, manages lessons/materials/assignments/quizzes/grades/attendance for owned courses. |
| University Administrator | Manages university-scoped announcements, events, scholarships, academic records, and verified student data. |
| Company / Employer | Maintains a company profile, purchases job-posting packages, posts jobs, and manages applicants. |
| Course Creator / Instructor | Creates and sells courses, manages course content, tracks learners, and receives earnings after platform commission. |
| Super Administrator | Manages the whole platform: users, roles, plans, payments, ads, sponsors, reports, settings, and moderation. |

Membership tier is separate from role. A user has one or more roles plus an active subscription tier. Free Student, Student Pro, and Student Premium are membership tiers of the Student role.

## Confirmed functional scope

### Core platform
- User registration, login, secure logout, password reset, email verification, profile management.
- Role-based access control with explicit roles, permissions, user-role assignments, and permission overrides.
- Account status lifecycle: pending, active, suspended, rejected.
- Responsive dashboard layout, navigation drawer, top bar, tabs, cards, lists, FAB, snackbars, banners, dialogs, empty/error/loading states.
- English and Khmer interface support, extending the existing i18n setup.

### Academic and learning
- Student dashboard with learning overview, deadlines, announcements, recommendations, notifications, and membership status.
- Learning resources: PDFs, documents, e-books, videos, categories, search/filter, free and premium gating.
- Class timetable, examination schedules, subject information, academic calendar, learning progress.
- Academic results and attendance with GPA tracking. Official records require verified administrator or university integration; students cannot self-assign official grades.
- Assignments, submissions, deadlines, lecturer feedback, quizzes, automatic scoring, and performance tracking.

### Opportunities and community
- Job and internship portal with company profiles, CV upload, applications, status tracking, employer dashboard, and paid job-posting packages.
- Scholarship listings, details, eligibility requirements, deadlines, categories, and application links.
- Discussion forum with posts, comments, likes, saves, reports, and moderation.
- Events, workshops, seminars, competitions, registration, and participation tracking.
- Help center with FAQ, contact support, complaints, technical issue reports, feedback, and support tickets.

### Hybrid business model
- Subscription plans: FREE $0, STUDENT PRO $2/month, STUDENT PREMIUM $4/month, with monthly and yearly billing.
- Ad-free PRO/Premium experience enforced through entitlement checks.
- Advertisement campaigns with image/banner uploads, placements, start/end dates, packages ($20/$50/$100), approval, view/click statistics, and revenue reports.
- Job posting packages: Basic $5, Standard $10, Featured $20.
- Course marketplace with instructor pricing, enrollment, progress, reviews/ratings, instructor earnings, and configurable platform commission.
- Initial platform commission: 15%.
- Sponsorship management with sponsor registration, partnership requests, packages, sponsored content, partner profiles, contracts, and revenue tracking.

### Payments and finance
- Course payments, subscription payments, job-posting payments, advertisement payments, and sponsorship payments.
- Payment methods, transaction reference numbers, pending/successful/failed/refunded statuses, admin verification, invoices, receipts, and refund workflow.
- Payment gateway integration must support Cambodia-relevant providers when merchant approval is available. Until then, manual verification remains the only confirmation path.
- No fake payment success. No raw bank card data or passwords stored.
- Financial reports for total revenue, ad revenue, subscription revenue, job-posting revenue, course commission, sponsorship revenue, expenses, and net operating income.
- Daily, weekly, monthly, and yearly report periods with Excel and PDF export.

### Administration and analytics
- Super Admin dashboard KPIs: students, active users, free/premium memberships, companies, instructors, courses, jobs, ads, monthly revenue, transactions, pending payments, refund requests.
- Interactive charts: revenue, registration growth, subscriptions, transactions, popular courses, and revenue by source.
- Admin management for users/roles, learning resources, courses, jobs, scholarships, ads, subscriptions, payments, sponsorships, reports, and site settings.
- DRF API for every module, JWT authentication, role-scoped querysets, throttling, and API documentation.

## Confirmed business rules

1. A payment becomes successful only after admin verification or a verified gateway webhook.
2. Enrollment, subscription activation, ad activation, job activation, and sponsorship activation happen only from a successful payment.
3. Refunds do not automatically create negative revenue without a finance ledger entry; the finance ledger must record adjustments.
4. Premium entitlement is computed from an active subscription, not from a manually edited flag.
5. Ads are always clearly labeled and must not block lessons, quizzes, or exams.
6. Official grades and attendance can only be created or changed by authorized university/admin accounts; all changes are audit logged.
7. Platform commission defaults to 15% and is configurable by Super Admin.
8. Prices are configured in USD initially; currency display may be extended to KHR using an exchange-rate setting.
9. Sensitive values come from environment variables. Secrets are never committed.
10. Existing project code and data are preserved during migration to the expanded scope.

## Out of scope for Phase 0–10

- Native Android/iOS applications. A responsive PWA web experience is in scope.
- Direct university SIS integration until an institution provides approved credentials and API contract.
- Automatic bank-card storage or recurring card charging. Gateway tokens may be stored only if the approved provider supports them.
- SMS notifications. Email and in-app notifications are in scope.
- Production deployment until Phase 10 and merchant/provider approvals are complete.

## Phase gates

| Phase | Gate |
| --- | --- |
| 0 Scope and ERD | This document, `docs/ROLE_MATRIX.md`, and updated `docs/ERD.md` approved. |
| 1 Foundation and RBAC | Core app, role/permission models, settings split, navigation and tests pass. |
| 2 Auth and profiles | Reset, verification, SMTP, profiles, account status, tests pass. |
| 3 Academic core | Timetable, calendar, GPA weighting, official-record restrictions, tests pass. |
| 4 Opportunities/community | Careers, scholarships, forum, events, support, tests pass. |
| 5 Monetization | Plans, entitlements, ads, sponsorships, commission, tests pass. |
| 6 Finance/reporting | Ledger, reports, exports, admin charts, tests pass. |
| 7 API/services | Versioned API, blacklist, throttles, OpenAPI, tests pass. |
| 8 UI/UX | Full design system, responsive/a11y checks, tests pass. |
| 9 Security/testing/backup | Security tests, backup command, clean full suite. |
| 10 Deployment/docs | Production settings, deployment guide, final documentation. |

Phase 1 status: implemented. The `apps.core` app, RBAC models, `core_role`/`core_permission` data, settings split, `seed_roles` command, and RBAC tests are in place.

Phase 2 status: implemented. Email verification, password reset, company/instructor registration, account-status enforcement, and role/permission display on the profile page are in place.

Phase 3 status: implemented. The `apps.academic` app provides class timetables, academic calendars, exam schedules, role-scoped visibility, and schedule management. Weighted GPA helpers, official grade-entry permission checks, grade audit logging, permission-gated attendance recording, attendance audit logging, and 7 Phase 3 tests are in place.

Phase 4 status: implemented. The `apps.careers`, `apps.scholarships`, `apps.community`, `apps.events`, and `apps.support` apps provide company profiles, paid job packages, job applications, scholarship applications, forum posts/comments/likes/saves/reports with moderation, event registration with exclusive-workshop gating, and help-center FAQs/tickets/feedback. Migrations, baseline seed data (`seed_phase4`), permission-gated navigation, public/private templates, and 25 Phase 4 tests are in place.

## Acceptance rule

A phase is not complete until migrations are applied, URLs and navigation are wired, templates and API endpoints work, role permissions are enforced, tests are added, and both `python manage.py check` and `python manage.py test` pass.
