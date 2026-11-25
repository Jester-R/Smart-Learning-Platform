from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.analytics.models import ActivityLog

from .forms import ForumCommentForm, ForumPostForm, ForumReportForm
from .models import ForumCategory, ForumLike, ForumPost, ForumReport, ForumSave


def _require_permission(user, code):
    if not user.is_authenticated or not user.has_permission(code):
        raise PermissionDenied("You do not have permission for this action.")


def forum_list(request):
    posts = ForumPost.objects.filter(is_hidden=False).select_related("author", "category")
    categories = ForumCategory.objects.annotate(
        post_count=Count("posts", filter=Q(posts__is_hidden=False))
    )
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(body__icontains=query))
    if category_slug:
        posts = posts.filter(category__slug=category_slug)
    return render(
        request,
        "community/forum_list.html",
        {
            "posts": posts,
            "query": query,
            "categories": categories,
            "category_slug": category_slug,
        },
    )


@login_required
def post_detail(request, pk):
    post = get_object_or_404(ForumPost, pk=pk, is_hidden=False)
    comments = post.comments.filter(is_hidden=False).select_related("author")
    liked = ForumLike.objects.filter(post=post, user=request.user).exists()
    saved = ForumSave.objects.filter(post=post, user=request.user).exists()
    return render(
        request,
        "community/post_detail.html",
        {"post": post, "comments": comments, "liked": liked, "saved": saved, "comment_form": ForumCommentForm()},
    )


@login_required
def post_create(request):
    _require_permission(request.user, "forum.post")
    form = ForumPostForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.CREATE,
            model_name="ForumPost",
            object_id=post.pk,
            description=f"Created forum post {post.title}",
        )
        messages.success(request, "Discussion posted.")
        return redirect("community:post_detail", pk=post.pk)
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "New discussion", "cancel_url": "community:forum_list"},
    )


@login_required
def comment_create(request, pk):
    _require_permission(request.user, "forum.comment")
    post = get_object_or_404(ForumPost, pk=pk, is_hidden=False)
    if post.is_locked:
        raise PermissionDenied("This discussion is locked.")
    form = ForumCommentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        messages.success(request, "Comment added.")
        return redirect("community:post_detail", pk=post.pk)
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "Add comment", "cancel_url": "community:forum_list"},
    )


@login_required
def toggle_like(request, pk):
    _require_permission(request.user, "forum.post")
    post = get_object_or_404(ForumPost, pk=pk, is_hidden=False)
    like = ForumLike.objects.filter(post=post, user=request.user).first()
    if like:
        like.delete()
    else:
        ForumLike.objects.create(post=post, user=request.user)
    return redirect("community:post_detail", pk=post.pk)


@login_required
def toggle_save(request, pk):
    _require_permission(request.user, "forum.post")
    post = get_object_or_404(ForumPost, pk=pk, is_hidden=False)
    saved = ForumSave.objects.filter(post=post, user=request.user).first()
    if saved:
        saved.delete()
    else:
        ForumSave.objects.create(post=post, user=request.user)
    return redirect("community:post_detail", pk=post.pk)


@login_required
def report_post(request, pk):
    _require_permission(request.user, "forum.post")
    post = get_object_or_404(ForumPost, pk=pk, is_hidden=False)
    form = ForumReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.post = post
        report.reporter = request.user
        report.save()
        messages.success(request, "Report submitted for moderation.")
        return redirect("community:post_detail", pk=post.pk)
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "Report post", "cancel_url": "community:forum_list"},
    )


@login_required
def moderation_list(request):
    _require_permission(request.user, "forum.moderate")
    return render(
        request,
        "community/moderation.html",
        {
            "reports": ForumReport.objects.filter(is_resolved=False).select_related(
                "post", "reporter"
            ),
            "posts": ForumPost.objects.filter(is_hidden=True),
        },
    )


@login_required
def moderate_post(request, pk):
    _require_permission(request.user, "forum.moderate")
    post = get_object_or_404(ForumPost, pk=pk)
    post.is_hidden = not post.is_hidden
    post.save()
    ActivityLog.objects.create(
        user=request.user,
        action=ActivityLog.Action.UPDATE,
        model_name="ForumPost",
        object_id=post.pk,
        description=f"{'Hid' if post.is_hidden else 'Restored'} forum post {post.title}",
    )
    messages.success(request, "Forum post visibility updated.")
    return redirect("community:moderation")
