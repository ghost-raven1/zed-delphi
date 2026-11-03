use language_model::LanguageModel;

#[derive(Clone, Debug)]
pub struct AnthropicEventData {
    pub completion_type: AnthropicCompletionType,
    pub event: AnthropicEventType,
    pub language_name: Option<String>,
    pub message_id: Option<String>,
}

#[derive(Clone, Debug)]
pub enum AnthropicCompletionType {
    Editor,
    Terminal,
    Panel,
}

#[derive(Clone, Debug)]
pub enum AnthropicEventType {
    Invoked,
    Response,
    Accept,
    Reject,
}

/// Compatibility hook; this fork never reports provider usage events.
pub fn report_anthropic_event(_model: &LanguageModel, _event: AnthropicEventData, _cx: &gpui::App) {
}

#[derive(Clone)]
pub struct AnthropicEventReporter;

impl AnthropicEventReporter {
    pub fn new(_model: &LanguageModel, _cx: &gpui::App) -> Self {
        Self
    }
    pub fn report(&self, _event: AnthropicEventData) {}
}
