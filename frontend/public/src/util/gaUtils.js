import ga4 from "react-ga4"

export function sendGAEvent({ category, action, label, value }) {
  const event = {
    category: category,
    action:   action,
    label:    label,
  }
  if (value !== undefined) {
    event.value = value
  }
  ga4.event(event)
}

export function sendGAEcommerceEvent({ eventType, eventData }) {
  ga4.gtag("event", eventType, eventData)
}
