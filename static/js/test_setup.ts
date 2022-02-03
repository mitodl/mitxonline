// Define globals we would usually get from Django
import "@testing-library/jest-dom"
import Enzyme from "enzyme"
import Adapter from "enzyme-adapter-react-16"
import failOnConsole from "jest-fail-on-console"
import "jest-location-mock"
import ReactDOM from "react-dom"

failOnConsole()

Enzyme.configure({ adapter: new Adapter() })

const _createSettings = (): Settings => ({
  reactGaDebug:    "",
  gaTrackingID:    "",
  public_path:     "",
  environment:     "",
  release_version: "0.0.0",
  sentry_dsn:      "",
  support_email:   "admin@localhost",
  site_name:       "MITx Online",
  recaptchaKey:    null,
  user:            {
    username: "example",
    name:     "Jane Doe",
    email:    "jane@example.com"
  }
})

globalThis.SETTINGS = _createSettings()
globalThis._testing = true

beforeEach(() => {
  globalThis.fetch = jest.fn()
})

// cleanup after each test run
// eslint-disable-next-line mocha/no-top-level-hooks
afterEach(function() {
  const node = document.querySelector("#integration_test_div")
  if (node) {
    ReactDOM.unmountComponentAtNode(node)
  }
  document.body.innerHTML = ""
  globalThis.SETTINGS = _createSettings()
})
