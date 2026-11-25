"""Export published lessons as formatted PDF files."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.courses.models import Course

from apps.learning.pdf_export import render_course_pack_pdf, render_lesson_pdf


class Command(BaseCommand):
    help = "Render every published lesson of one or more courses into well-formatted PDF files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--course",
            metavar="SLUG",
            help="Course slug to export. Defaults to every course with published lessons.",
        )
        parser.add_argument(
            "--out",
            default=None,
            help="Output directory. Defaults to MEDIA_ROOT/lesson_pdfs.",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        courses = Course.objects.prefetch_related("lessons")
        if options["course"]:
            courses = courses.filter(slug=options["course"])
            if not courses.exists():
                raise CommandError(f"Course '{options['course']}' was not found.")

        out_dir = Path(options["out"]) if options["out"] else Path(settings.MEDIA_ROOT) / "lesson_pdfs"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = timezone.localtime().strftime("%Y-%m-%d")
        exported = 0

        for course in courses:
            lessons = course.lessons.filter(is_published=True).order_by("order")
            if not lessons.exists():
                self.stdout.write(f"Skipping {course.code} (no published lessons).")
                continue

            course_dir = out_dir / course.slug
            course_dir.mkdir(parents=True, exist_ok=True)
            for lesson in lessons:
                target = course_dir / f"{lesson.order:02d}-{lesson.title}.pdf"
                safe_name = "".join(
                    c if c.isalnum() or c in "-_ " else "-" for c in target.stem
                )
                target = target.with_name(safe_name.strip() + ".pdf")
                with target.open("wb") as handle:
                    render_lesson_pdf(lesson, handle)
                exported += 1
                self.stdout.write(f"Wrote {target}")

            pack = course_dir / f"{course.slug}-lesson-pack-{stamp}.pdf"
            with pack.open("wb") as handle:
                render_course_pack_pdf(course, handle)
            self.stdout.write(f"Wrote {pack}")
            self.stdout.write(self.style.SUCCESS(f"{course.code}: {lessons.count()} lessons exported."))

        self.stdout.write(self.style.SUCCESS(f"Done. {exported} lesson PDFs written to {out_dir}"))
