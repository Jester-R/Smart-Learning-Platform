/**
 * YouTube Learning Module - Frontend Scripts
 * Handles YouTube URL validation, live preview, responsive playback, and progress updates.
 */

(function () {
    'use strict';

    // 11-character base64url regex matching standard YouTube video IDs
    const YOUTUBE_ID_RE = /^[A-Za-z0-9_-]{11}$/;

    /**
     * Extracts an 11-character YouTube video ID from supported URL patterns:
     * - https://www.youtube.com/watch?v=VIDEO_ID
     * - https://youtu.be/VIDEO_ID
     * - https://www.youtube.com/embed/VIDEO_ID
     * - https://www.youtube.com/shorts/VIDEO_ID
     * - https://www.youtube.com/live/VIDEO_ID
     */
    function extractYouTubeId(url) {
        if (!url || typeof url !== 'string') return null;
        url = url.trim();
        if (!url) return null;

        // Ensure scheme for standard URL parsing
        if (!/^https?:\/\//i.test(url)) {
            url = 'https://' + url;
        }

        try {
            const parsed = new URL(url);
            const host = parsed.hostname.toLowerCase();

            const validHosts = [
                'youtube.com',
                'www.youtube.com',
                'm.youtube.com',
                'youtu.be',
                'www.youtu.be',
                'youtube-nocookie.com',
                'www.youtube-nocookie.com'
            ];

            if (!validHosts.includes(host)) {
                return null;
            }

            let candidate = null;

            // Short URL format: youtu.be/ID
            if (host === 'youtu.be' || host === 'www.youtu.be') {
                const pathParts = parsed.pathname.replace(/^\/+|\/+$/g, '').split('/');
                candidate = pathParts[0] || null;
            } else if (parsed.pathname === '/watch' || parsed.pathname.startsWith('/watch')) {
                // Watch URL: youtube.com/watch?v=ID
                candidate = parsed.searchParams.get('v');
            } else {
                // Path-based: /embed/ID, /shorts/ID, /live/ID
                const prefixes = ['/embed/', '/shorts/', '/live/', '/v/'];
                for (const p of prefixes) {
                    if (parsed.pathname.startsWith(p)) {
                        const remainder = parsed.pathname.substring(p.length).replace(/\/.*$/, '');
                        candidate = remainder;
                        break;
                    }
                }
            }

            if (candidate && YOUTUBE_ID_RE.test(candidate)) {
                return candidate;
            }
        } catch (e) {
            return null;
        }

        return null;
    }

    /**
     * Live Preview Initializer for Lesson Creation/Edit Forms
     */
    function initYouTubeFormPreview() {
        const input = document.getElementById('id_youtube_url');
        const previewContainer = document.getElementById('youtube-preview-container');
        const previewIframe = document.getElementById('youtube-preview-iframe');
        const previewFeedback = document.getElementById('youtube-preview-feedback');
        const previewThumb = document.getElementById('youtube-preview-thumb');
        const previewWatchLink = document.getElementById('youtube-preview-watch-link');

        if (!input || !previewContainer || !previewIframe) {
            return;
        }

        let debounceTimer = null;

        function updatePreview() {
            const rawUrl = input.value.trim();
            const videoId = extractYouTubeId(rawUrl);

            if (videoId) {
                const embedUrl = `https://www.youtube-nocookie.com/embed/${videoId}?rel=0&modestbranding=1&enablejsapi=1`;
                const watchUrl = `https://www.youtube.com/watch?v=${videoId}`;
                const thumbUrl = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;

                if (previewIframe.getAttribute('data-loaded-id') !== videoId) {
                    previewIframe.src = embedUrl;
                    previewIframe.setAttribute('data-loaded-id', videoId);
                }

                previewContainer.classList.remove('d-none');
                if (previewFeedback) {
                    previewFeedback.innerHTML = `
                        <div class="alert alert-success d-flex align-items-center gap-2 py-2 px-3 mb-0">
                            <i class="bi bi-check-circle-fill text-success fs-5"></i>
                            <div>
                                <strong>Valid YouTube Video</strong> &bull; ID: <code>${videoId}</code>
                                <a href="${watchUrl}" target="_blank" rel="noopener" class="ms-2 small text-decoration-none">Open on YouTube &nearr;</a>
                            </div>
                        </div>
                    `;
                }
                if (previewThumb) {
                    previewThumb.src = thumbUrl;
                    previewThumb.classList.remove('d-none');
                }
                if (previewWatchLink) {
                    previewWatchLink.href = watchUrl;
                    previewWatchLink.classList.remove('d-none');
                }
            } else if (rawUrl.length > 0) {
                previewContainer.classList.add('d-none');
                previewIframe.src = '';
                previewIframe.removeAttribute('data-loaded-id');
                if (previewFeedback) {
                    previewFeedback.innerHTML = `
                        <div class="alert alert-warning d-flex align-items-center gap-2 py-2 px-3 mb-0">
                            <i class="bi bi-exclamation-triangle-fill text-warning fs-5"></i>
                            <div>Enter a valid YouTube URL (e.g. <code>https://www.youtube.com/watch?v=VIDEO_ID</code> or <code>https://youtu.be/VIDEO_ID</code>).</div>
                        </div>
                    `;
                }
            } else {
                previewContainer.classList.add('d-none');
                previewIframe.src = '';
                previewIframe.removeAttribute('data-loaded-id');
                if (previewFeedback) {
                    previewFeedback.innerHTML = '';
                }
            }
        }

        input.addEventListener('input', function () {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(updatePreview, 300);
        });

        input.addEventListener('change', updatePreview);
        input.addEventListener('paste', function () {
            setTimeout(updatePreview, 100);
        });

        // Run once on load if initial value exists
        if (input.value) {
            updatePreview();
        }
    }

    /**
     * AJAX "Mark as Completed" on Lesson Detail Page
     */
    function initLessonCompletion() {
        const form = document.getElementById('mark-complete-form');
        if (!form) return;

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Saving...';
            }

            const actionUrl = form.action;
            const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

            fetch(actionUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                },
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Server returned ' + response.status);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        // Replace form with Completed badge
                        const container = form.parentElement;
                        if (container) {
                            container.innerHTML = `
                                <span class="badge text-bg-success py-2 px-3 d-inline-flex align-items-center gap-1">
                                    <i class="bi bi-check-circle-fill"></i> Completed
                                </span>
                            `;
                        }

                        // Update progress bar
                        const progressBar = document.getElementById('course-progress-bar');
                        const progressText = document.getElementById('course-progress-percent');
                        const completedCount = document.getElementById('course-completed-count');

                        if (progressBar && data.progress_percent !== undefined) {
                            const rounded = Math.round(data.progress_percent);
                            progressBar.style.width = rounded + '%';
                            progressBar.setAttribute('aria-valuenow', rounded);
                        }
                        if (progressText && data.progress_percent !== undefined) {
                            progressText.textContent = Math.round(data.progress_percent) + '%';
                        }
                        if (completedCount && data.completed_count !== undefined && data.total_count !== undefined) {
                            completedCount.textContent = `${data.completed_count} of ${data.total_count} lessons completed`;
                        }

                        // Update active lesson checkmark in playlist
                        const activePlaylistItem = document.querySelector('.lesson-playlist-item.active');
                        if (activePlaylistItem) {
                            const statusIcon = activePlaylistItem.querySelector('.lesson-status-icon');
                            if (statusIcon) {
                                statusIcon.innerHTML = '<i class="bi bi-check-circle-fill text-success" title="Completed"></i>';
                            }
                        }
                    } else {
                        alert(data.error || 'Failed to mark lesson complete.');
                        if (submitBtn) {
                            submitBtn.disabled = false;
                            submitBtn.innerHTML = '<i class="bi bi-check2-circle me-1"></i> Mark as Completed';
                        }
                    }
                })
                .catch(err => {
                    // Fall back to standard form submit if fetch fails
                    form.submit();
                });
        });
    }

    /**
     * Teacher Video Preview Modal Handler
     */
    function initVideoPreviewModal() {
        const modalEl = document.getElementById('videoPreviewModal');
        if (!modalEl) return;

        const modalTitle = document.getElementById('videoPreviewModalTitle');
        const modalIframe = document.getElementById('videoPreviewModalIframe');
        const modalWatchLink = document.getElementById('videoPreviewModalWatchLink');

        modalEl.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            if (!button) return;

            const videoId = button.getAttribute('data-video-id');
            const title = button.getAttribute('data-video-title') || 'YouTube Video Preview';

            if (modalTitle) modalTitle.textContent = title;
            if (modalIframe && videoId) {
                modalIframe.src = `https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&rel=0&modestbranding=1`;
            }
            if (modalWatchLink && videoId) {
                modalWatchLink.href = `https://www.youtube.com/watch?v=${videoId}`;
            }
        });

        // Clear iframe on close so video stops playing
        modalEl.addEventListener('hidden.bs.modal', function () {
            if (modalIframe) {
                modalIframe.src = '';
            }
        });
    }

    /**
     * AJAX Toggle Publish for Teacher Video Management
     */
    function initPublishToggles() {
        document.querySelectorAll('.toggle-publish-btn').forEach(button => {
            button.addEventListener('click', function (e) {
                e.preventDefault();
                const url = this.getAttribute('data-toggle-url');
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
                    document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

                if (!url) return;

                const badge = this.closest('tr')?.querySelector('.status-badge');
                this.disabled = true;

                fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json',
                    },
                })
                    .then(res => res.json())
                    .then(data => {
                        this.disabled = false;
                        if (data.success) {
                            if (badge) {
                                if (data.is_published) {
                                    badge.className = 'badge text-bg-success status-badge';
                                    badge.textContent = 'Published';
                                } else {
                                    badge.className = 'badge text-bg-warning status-badge';
                                    badge.textContent = 'Draft';
                                }
                            }
                            this.innerHTML = data.is_published
                                ? '<i class="bi bi-eye-slash"></i> Unpublish'
                                : '<i class="bi bi-eye"></i> Publish';
                        }
                    })
                    .catch(() => {
                        this.disabled = false;
                        window.location.reload();
                    });
            });
        });
    }

    // Initialize all components on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', function () {
        initYouTubeFormPreview();
        initLessonCompletion();
        initVideoPreviewModal();
        initPublishToggles();
    });

    // Expose helpers globally if needed
    window.SLP = window.SLP || {};
    window.SLP.extractYouTubeId = extractYouTubeId;
})();

