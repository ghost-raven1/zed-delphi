use crate::{EditPredictionStore, StoredEvent};

use anyhow::Context as _;
use buffer_diff::BufferDiffSnapshot;
use collections::HashMap;
use gpui::{Context, Entity, Task};
use language::BufferSnapshot;
use project::{Project, ProjectPath, WorktreeId};
use std::{fmt::Write as _, ops::Range, path::Path, sync::Arc};
use text::Point;
use util::rel_path::RelPath;

pub type UncommittedDiffSnapshot = Vec<(Arc<Path>, BufferSnapshot, BufferDiffSnapshot)>;
pub type UncommittedDiffResult = std::result::Result<UncommittedDiffSnapshot, Arc<anyhow::Error>>;

pub use zeta_prompt::udiff::CURSOR_POSITION_MARKER;

pub fn uncommitted_diffs_for_events(
    project: Entity<Project>,
    worktree_id: WorktreeId,
    events: Vec<StoredEvent>,
    cx: &Context<'_, EditPredictionStore>,
) -> Task<UncommittedDiffResult> {
    let git_store = project.read_with(cx, |project, _| project.git_store().clone());

    cx.spawn(async move |_store, cx| {
        let (worktree_root_name, worktree_abs_path, path_style) = project
            .read_with(cx, |project, cx| {
                let worktree = project.worktree_for_id(worktree_id, cx)?;
                let worktree = worktree.read(cx);
                let path_style = worktree.path_style();
                let root_name = RelPath::new(Path::new(worktree.root_name_str()), path_style)
                    .ok()?
                    .into_owned();
                Some((root_name, worktree.abs_path(), path_style))
            })
            .context("failed to find worktree for uncommitted diff capture")
            .map_err(Arc::new)?;

        let events_with_paths = events
            .into_iter()
            .filter_map(|stored_event| {
                let zeta_prompt::Event::BufferChange { path, .. } = stored_event.event.as_ref();
                let path = if let Ok(path) = RelPath::new(path, path_style) {
                    path.strip_prefix(&worktree_root_name).ok()?.into_arc()
                } else {
                    let path = path.strip_prefix(worktree_abs_path.as_ref()).ok()?;
                    RelPath::new(path, path_style).ok()?.into_arc()
                };
                let project_path = ProjectPath { worktree_id, path };
                let relative_path: Arc<Path> = project_path.path.as_std_path().into();
                Some((stored_event, project_path, relative_path))
            })
            .collect::<Vec<_>>();

        let mut snapshots_by_path: HashMap<Arc<Path>, (BufferSnapshot, BufferDiffSnapshot)> =
            HashMap::default();
        for (stored_event, project_path, relative_path) in events_with_paths.iter().rev() {
            if snapshots_by_path.contains_key(relative_path) {
                continue;
            }

            let buffer = project
                .update(cx, |project, cx| {
                    project.open_buffer(project_path.clone(), cx)
                })
                .await
                .context("failed to open buffer for uncommitted diff capture")
                .map_err(Arc::new)?;
            let buffer_id = buffer.read_with(cx, |buffer, _| buffer.remote_id());
            let file_context = stored_event.file_context.clone();
            let cached_diff = file_context
                .as_ref()
                .and_then(|file_context| {
                    file_context
                        .read_with(cx, |file_context, _| file_context.uncommitted_diff.clone())
                })
                // The cached diff is keyed by path, but its hunk anchors are pinned to a
                // specific buffer. If that buffer was closed and reopened, `open_buffer`
                // hands back a buffer with a new `BufferId`; reusing the stale diff against
                // it would mix anchors from different buffers and panic. Drop the cache in
                // that case so the diff is recomputed for the current buffer.
                .filter(|diff| diff.read_with(cx, |diff, _| diff.buffer_id) == buffer_id);
            let diff = match cached_diff {
                Some(diff) => diff,
                None => {
                    let diff = git_store
                        .update(cx, |git_store, cx| {
                            git_store.open_uncommitted_diff(buffer.clone(), cx)
                        })
                        .await
                        .context("failed to open uncommitted diff for capture")
                        .map_err(Arc::new)?;
                    if let Some(file_context) = file_context {
                        file_context.update(cx, |file_context, _| {
                            file_context.uncommitted_diff = Some(diff.clone());
                        });
                    }
                    diff
                }
            };

            let buffer_snapshot = buffer.update(cx, |buffer, _| buffer.snapshot());
            let diff_snapshot = diff.update(cx, |diff, cx| diff.snapshot(cx));
            snapshots_by_path.insert(relative_path.clone(), (buffer_snapshot, diff_snapshot));
        }

        let uncommitted_diff_snapshots = snapshots_by_path
            .into_iter()
            .map(|(relative_path, (snapshot, diff_snapshot))| {
                (relative_path, snapshot, diff_snapshot)
            })
            .collect();

        Ok(uncommitted_diff_snapshots)
    })
}

pub fn compute_cursor_excerpt(
    snapshot: &language::BufferSnapshot,
    cursor_anchor: language::Anchor,
) -> (String, usize, Range<Point>) {
    use text::ToOffset as _;
    use text::ToPoint as _;

    let cursor_offset = cursor_anchor.to_offset(snapshot);
    let (excerpt_point_range, excerpt_offset_range, cursor_offset_in_excerpt) =
        crate::cursor_excerpt::compute_cursor_excerpt(snapshot, cursor_offset);
    let syntax_ranges = crate::cursor_excerpt::compute_syntax_ranges(
        snapshot,
        cursor_offset,
        &excerpt_offset_range,
    );
    let excerpt_text: String = snapshot.text_for_range(excerpt_point_range).collect();
    let (_, context_range) = zeta_prompt::compute_editable_and_context_ranges(
        &excerpt_text,
        cursor_offset_in_excerpt,
        &syntax_ranges,
        100,
        50,
    );
    let context_text = excerpt_text[context_range.clone()].to_string();
    let cursor_in_context = cursor_offset_in_excerpt.saturating_sub(context_range.start);
    let context_buffer_start =
        (excerpt_offset_range.start + context_range.start).to_point(snapshot);
    let context_buffer_end = (excerpt_offset_range.start + context_range.end).to_point(snapshot);
    (
        context_text,
        cursor_in_context,
        context_buffer_start..context_buffer_end,
    )
}

pub fn format_cursor_excerpt(
    excerpt: &str,
    cursor_offset: usize,
    line_comment_prefix: &str,
) -> String {
    let cursor_line_start = excerpt[..cursor_offset]
        .rfind('\n')
        .map(|pos| pos + 1)
        .unwrap_or(0);
    let cursor_line_end = excerpt[cursor_line_start..]
        .find('\n')
        .map(|pos| cursor_line_start + pos + 1)
        .unwrap_or(excerpt.len());
    let cursor_line = &excerpt[cursor_line_start..cursor_line_end];
    let cursor_line_indent = &cursor_line[..cursor_line.len() - cursor_line.trim_start().len()];
    let cursor_column = cursor_offset - cursor_line_start;

    let mut marker_line = String::new();
    if cursor_column < line_comment_prefix.len() {
        for _ in 0..cursor_column {
            marker_line.push(' ');
        }
        marker_line.push_str(line_comment_prefix);
        write!(marker_line, " <{}", CURSOR_POSITION_MARKER).unwrap();
    } else {
        if cursor_column >= cursor_line_indent.len() + line_comment_prefix.len() {
            marker_line.push_str(cursor_line_indent);
        }
        marker_line.push_str(line_comment_prefix);
        while marker_line.len() < cursor_column {
            marker_line.push(' ');
        }
        write!(marker_line, "^{}", CURSOR_POSITION_MARKER).unwrap();
    }

    let mut result = String::with_capacity(excerpt.len() + marker_line.len() + 2);
    result.push_str(&excerpt[..cursor_line_end]);
    if !result.ends_with('\n') {
        result.push('\n');
    }
    result.push_str(&marker_line);
    if cursor_line_end < excerpt.len() {
        result.push('\n');
        result.push_str(&excerpt[cursor_line_end..]);
    }
    result
}
