import { isIf, shouldIf } from "../../../lib/test_utils"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import RegisterDeniedPage from "./RegisterDeniedPage"

describe("RegisterDeniedPage", () => {
  const error = "errorTestValue"
  const email = "email@localhost"
  let helper: IntegrationTestHelper, renderPage: TestRenderer

  beforeEach(() => {
    SETTINGS.support_email = email
    helper = new IntegrationTestHelper()
    renderPage = helper.configureRenderer(RegisterDeniedPage)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("displays a link to email support", async () => {
    const { wrapper } = await renderPage()
    expect(wrapper.find("a").prop("href")).toEqual(`mailto:${email}`)
  })
  ;[true, false].forEach(hasError => {
    it(`${shouldIf(hasError)} show an error message if ${isIf(
      hasError
    )} in the query string`, async () => {
      helper.browserHistory.push(hasError ? `/?error=${error}` : "")
      const { wrapper } = await renderPage()
      const detail = wrapper.find(".error-detail")
      expect(detail.exists()).toEqual(hasError)

      if (hasError) {
        expect(detail.text()).toEqual(error)
      }
    })
  })
})
