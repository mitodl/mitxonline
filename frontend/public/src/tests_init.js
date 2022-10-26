// Define globals we would usually get from Django
import ReactDOM from "react-dom"
import { configure } from "enzyme"
import Adapter from "enzyme-adapter-react-16"
import { JSDOM } from "jsdom"

// jsdom initialization here adapted from https://airbnb.io/enzyme/docs/guides/jsdom.html

const jsdom = new JSDOM("<!doctype html><html><body></body></html>")
const { window } = jsdom

const { polyfill } = require("raf")

polyfill(global)
polyfill(window)

// polyfill for the web crypto module
window.crypto = require("@trust/webcrypto")

// We need to explicitly change the URL when window.location is used

function copyProps(src, target) {
  Object.defineProperties(target, {
    ...Object.getOwnPropertyDescriptors(src),
    ...Object.getOwnPropertyDescriptors(target)
  })
}

global.window = window
global.document = window.document
global.navigator = {
  userAgent: "node.js"
}
global.requestAnimationFrame = function(callback) {
  return setTimeout(callback, 0)
}
global.cancelAnimationFrame = function(id) {
  clearTimeout(id)
}
copyProps(window, global)

Object.defineProperty(window, "location", {
  set: value => {
    if (!value.startsWith("http")) {
      value = `http://fake${value}`
    }
    jsdom.reconfigure({ url: value })
  }
})

configure({ adapter: new Adapter() })

const _createSettings = () => ({})

global.SETTINGS = _createSettings()
global.TESTING = true
global.CSOURCE_PAYLOAD = null

// cleanup after each test run
// eslint-disable-next-line mocha/no-top-level-hooks
afterEach(function() {
  const node = document.querySelector("#integration_test_div")
  if (node) {
    ReactDOM.unmountComponentAtNode(node)
  }
  document.body.innerHTML = ""
  global.SETTINGS = _createSettings()
  window.location = "http://fake/"
})

// enable chai-as-promised
import chai from "chai"
import chaiAsPromised from "chai-as-promised"
chai.use(chaiAsPromised)
