use project::ContextProviderWithTasks;
use task::{SaveStrategy, TaskTemplate, TaskTemplates, VariableName};

/// File-level FPC tasks work without a project manifest; project builds use explicit tasks.
pub(super) fn task_context() -> ContextProviderWithTasks {
    ContextProviderWithTasks::new(TaskTemplates(vec![
        TaskTemplate {
            label: "Delphi: compile current file with Free Pascal (Debug)".into(),
            // Tasks and debugger build steps quote args differently; keep the shell command whole.
            command: format!(
                "fpc -Mdelphi -g -gl -gw3 -O- {}",
                VariableName::File.template_value_with_whitespace()
            ),
            cwd: Some(VariableName::Dirname.template_value()),
            save: SaveStrategy::All,
            ..TaskTemplate::default()
        },
        TaskTemplate {
            label: "Delphi: compile current file with Free Pascal (Release)".into(),
            command: format!(
                "fpc -Mdelphi -O2 {}",
                VariableName::File.template_value_with_whitespace()
            ),
            cwd: Some(VariableName::Dirname.template_value()),
            save: SaveStrategy::All,
            ..TaskTemplate::default()
        },
    ]))
}
