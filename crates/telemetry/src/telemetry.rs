//! Telemetry is absent from this fork; these APIs preserve upstream call sites.
use futures::channel::mpsc;
pub use serde_json;
pub use telemetry_events::FlexibleEvent as Event;

/// Type-check properties without evaluating them, allocating, or collecting data.
#[macro_export]
macro_rules! event {
    ($name:expr) => {{ if false { let _ = &$name; } }};
    ($name:expr, $($key:ident $(= $value:expr)?),+ $(,)?) => {{
        if false {
            let _ = &$name;
            $(let _ = &$crate::serialize_property!($key $(= $value)?);)+
        }
    }};
}

#[macro_export]
macro_rules! serialize_property {
    ($key:ident) => {
        $key
    };
    ($key:ident = $value:expr) => {
        $value
    };
}

pub fn send_event(_event: Event) {}
pub fn init(_sender: mpsc::UnboundedSender<Event>) {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn properties_and_event_names_are_not_evaluated() {
        let calls = std::cell::Cell::new(0);
        event!(
            {
                calls.set(calls.get() + 1);
                "private-name"
            },
            value = {
                calls.set(calls.get() + 1);
                "private-value"
            }
        );
        assert_eq!(calls.get(), 0);
    }

    #[test]
    fn direct_events_are_never_forwarded() {
        let (sender, mut receiver) = mpsc::unbounded();
        init(sender);
        send_event(Event {
            event_type: "private".into(),
            event_properties: Default::default(),
        });
        assert!(matches!(
            receiver.try_recv(),
            Err(mpsc::TryRecvError::Closed)
        ));
    }
}
