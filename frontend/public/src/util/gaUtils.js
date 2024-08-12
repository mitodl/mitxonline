import ga4 from "react-ga4"

export function sendGAEvent({ category, action, label }) {
  let event = {
    category: category,
    action: action,
    label: label,
  }
  if (value !== undefined) {
    event.value = value
  }
  ga4.event(event)
}

export function sendGAEcommerceEvent({ event_type, event_data }) {
  ga4.gtag("event", event_type, event_data)
}
