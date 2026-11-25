# Role and Permission Matrix

This document defines the target authorization model for the All-in-One Student Portal. It complements `docs/SCOPE.md` and `docs/ERD.md`.

Phase 1 implementation note: `python manage.py seed_roles` creates 12 role rows and 70 permission rows. The extra `admin`, `teacher`, and `student` rows are legacy aliases that preserve existing accounts while the new codes are adopted.

## Model

- `roles.role` defines named platform roles.
- `roles.permission` defines permission codes such as `course.create` or `payment.verify`.
- `accounts.userrole` assigns one or more roles to a user.
- `accounts.userpermissionoverride` grants or denies a specific permission for a specific user.
- Membership tier (`FREE`, `STUDENT_PRO`, `STUDENT_PREMIUM`) is stored on the active subscription and is evaluated by `EntitlementService`.
- A user's effective permission is the union of all assigned role permissions, modified by explicit user overrides. Deny overrides win.

## Legend

| Value | Meaning |
| --- | --- |
| Full | Can create, read, update, and delete within authorized scope. |
| Own | Can manage only records they own or are explicitly assigned to. |
| Limited | Can read public/assigned records or perform a restricted action. |
| Approve | Can review and approve/reject records but not create them. |
| No | No access. |

## Role matrix

| Capability | Guest | Free Student | Student Pro | Student Premium | Lecturer / Teacher | University Admin | Company / Employer | Course Creator / Instructor | Super Admin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Browse public landing page | Full | Full | Full | Full | Full | Full | Full | Full | Full |
| Browse public courses/jobs/scholarships/events | Full | Full | Full | Full | Full | Full | Full | Full | Full |
| Register as student/company/instructor | Limited | No | No | No | No | No | Limited | Limited | Full |
| Login/logout/password reset | Limited | Full | Full | Full | Full | Full | Full | Full | Full |
| View personal dashboard | No | Full | Full | Full | Full | Full | Full | Full | Full |
| Manage own profile | No | Full | Full | Full | Full | Full | Full | Full | Full |
| Manage users and roles | No | No | No | No | No | Limited | No | No | Full |
| Set account status | No | No | No | No | No | Limited | No | No | Full |
| View free learning resources | Limited | Full | Full | Full | Full | Full | Full | Full | Full |
| View premium learning resources | No | No | Full | Full | Full | Full | No | Full | Full |
| Create/manage learning resources | No | No | No | No | Own | Limited | No | Own | Full |
| View class schedule/calendar | No | Full | Full | Full | Full | Full | No | Full | Full |
| Manage university schedule/calendar | No | No | No | No | Limited | Full | No | No | Full |
| View own grades/attendance | No | Full | Full | Full | Full | Full | No | Full | Full |
| Enter/change official grades or attendance | No | No | No | No | Own | Own | No | No | Limited |
| Audit grade changes | No | No | No | No | Limited | Full | No | Limited | Full |
| Submit assignments | No | Full | Full | Full | No | No | No | No | No |
| Grade assignments | No | No | No | No | Own | Limited | No | Own | Full |
| Take quizzes/exams | No | Full | Full | Full | No | No | No | No | No |
| Create quizzes/exams | No | No | No | No | Own | Limited | No | Own | Full |
| View announcements | Limited | Full | Full | Full | Full | Full | Limited | Full | Full |
| Create university announcements | No | No | No | No | Limited | Full | No | No | Full |
| Receive in-app/email notifications | No | Full | Full | Full | Full | Full | Full | Full | Full |
| Browse/apply to jobs | Limited | Full | Full | Full | No | No | No | No | Full |
| Create company profile | No | No | No | No | No | No | Own | No | Full |
| Post paid jobs | No | No | No | No | No | No | Own | No | Full |
| Approve job posts and packages | No | No | No | No | No | Limited | No | No | Full |
| Manage applicants | No | No | No | No | No | No | Own | No | Full |
| Browse scholarships | Limited | Full | Full | Full | Full | Full | Full | Full | Full |
| Manage scholarships | No | No | No | No | No | Full | No | No | Full |
| Create forum posts/comments | No | Full | Full | Full | Full | Full | Limited | Full | Full |
| Like/save posts | No | Full | Full | Full | Full | Full | Full | Full | Full |
| Report forum content | No | Full | Full | Full | Full | Full | Full | Full | Full |
| Moderate forum content | No | No | No | No | Limited | Full | No | Limited | Full |
| Register for events | No | Full | Full | Full | Full | Full | Limited | Full | Full |
| Manage events | No | No | No | No | Limited | Full | Limited | Limited | Full |
| Submit support tickets | No | Full | Full | Full | Full | Full | Full | Full | Full |
| priority support | No | No | Full | Full | No | No | No | No | Full |
| Manage support tickets | No | No | No | No | No | Limited | No | No | Full |
| Manage subscriptions/plans | No | No | No | No | No | No | No | No | Full |
| View own subscription history | No | Full | Full | Full | Full | Full | Full | Full | Full |
| Create/manage ad campaigns | No | No | No | No | No | No | Own | Limited | Full |
| Approve ads | No | No | No | No | No | Limited | No | No | Full |
| Create/manage sponsorships | No | No | No | No | No | Limited | Own | Limited | Full |
| View instructor earnings | No | No | No | No | No | No | No | Own | Full |
| Verify/reject payments | No | No | No | No | No | Limited | No | No | Full |
| View own invoices/receipts/refunds | No | Full | Full | Full | Full | Full | Full | Full | Full |
| Manage finance reports/expenses | No | No | No | No | No | No | No | No | Full |
| Manage platform settings | No | No | No | No | No | No | No | No | Full |
| View admin analytics | No | No | No | No | Limited | Full | No | Limited | Full |
| Use AI assistant | No | Full | Full | Full | Full | Full | Full | Full | Full |

## Membership entitlement matrix

| Feature | FREE | STUDENT PRO | STUDENT PREMIUM |
| --- | --- | --- | --- |
| Basic student dashboard | Yes | Yes | Yes |
| Free learning resources | Yes | Yes | Yes |
| Class schedule | Yes | Yes | Yes |
| Announcements | Yes | Yes | Yes |
| Job and scholarship listings | Yes | Yes | Yes |
| Student community | Yes | Yes | Yes |
| Ad-free experience | No | Yes | Yes |
| Premium study materials | No | Yes | Yes |
| Advanced practice tests | No | Yes | Yes |
| CV templates | No | Yes | Yes |
| Learning progress analytics | No | Yes | Yes |
| Premium online courses | No | No | Yes |
| Advanced learning resources | No | No | Yes |
| Career development materials | No | No | Yes |
| Exclusive workshops | No | No | Yes |
| Priority support | No | No | Yes |

## Permission code groups

| Group | Example codes |
| --- | --- |
| Identity | `user.view`, `user.create`, `user.update`, `user.delete`, `role.assign`, `account.status_change` |
| Academic | `schedule.view`, `schedule.manage`, `grade.view_own`, `grade.record`, `attendance.view_own`, `attendance.record` |
| Learning | `resource.view_free`, `resource.view_premium`, `resource.manage`, `course.create`, `course.manage_own`, `course.publish` |
| Assessment | `assignment.submit`, `assignment.grade`, `quiz.take`, `quiz.manage`, `exam.take`, `exam.manage` |
| Communication | `announcement.view`, `announcement.manage`, `notification.view_own`, `notification.send` |
| Opportunities | `job.view`, `job.apply`, `company.manage_own`, `job.post`, `job.approve`, `scholarship.view`, `scholarship.manage` |
| Community | `forum.post`, `forum.comment`, `forum.moderate`, `event.register`, `event.manage` |
| Support | `ticket.create`, `ticket.view_own`, `ticket.manage`, `faq.manage` |
| Commerce | `ad.manage_own`, `ad.approve`, `sponsor.manage_own`, `subscription.manage`, `payment.verify`, `refund.approve` |
| Reporting | `report.academic_view`, `report.finance_view`, `report.export`, `settings.manage` |

## Enforcement rules

1. Server-side checks are mandatory in views, DRF permissions/querysets, and management commands. Hiding a button is not authorization.
2. Object-level checks must verify ownership or assignment, not only role.
3. Official academic records require `grade.record` or `attendance.record` plus an assigned course/university scope.
4. Premium content requires an active subscription with the correct entitlement in addition to the student role.
5. Super Admin can override any permission, but sensitive actions such as finance edits and grade changes must be audit logged.
6. Deny overrides take precedence over role grants.
7. Every authorization denial should produce a user-friendly 403 page and an activity log entry where appropriate.
