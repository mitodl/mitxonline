// @flow
import { assert } from "chai"
import { shallow } from "enzyme"

import LearnerRecordsPage, {
  LearnerRecordsPage as InnerLearnerRecordsPage
} from "./LearnerRecordsPage"
import { makeLearnerRecord } from "../../../factories/course"
import IntegrationTestHelper from "../../../util/integration_test_helper"

describe("LearnerRecordsPage", () => {
  let helper, renderPage

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    global.SETTINGS = {
      site_name:     "MITx Online",
      support_email: "support@example.com"
    }

    renderPage = helper.configureShallowRenderer(
      LearnerRecordsPage,
      InnerLearnerRecordsPage,
      {},
      {
        learnerRecord:       null,
        isSharedRecord:      false,
        history:             {},
        isLoading:           false,
        addUserNotification: helper.sandbox.stub(),
        forceRequest:        helper.sandbox.stub(),
        enableRecordSharing: helper.sandbox.stub().resolves({}),
        revokeRecordSharing: helper.sandbox.stub().resolves({}),
        match:               { params: { program: "1" } },
        currentUser:         { is_authenticated: true }
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
    delete global.SETTINGS
  })

  it("keeps the records page title banner", async () => {
    const { inner } = await renderPage()
    const pageHeader = inner.find(".std-page-header").first()

    assert.isTrue(pageHeader.exists())
    assert.equal(pageHeader.find("h1").first().text(), "Program Record")
  })

  it("renders the MIT logo in the learner record header", async () => {
    const learnerRecord = makeLearnerRecord(true)
    const { inner } = await renderPage({}, { learnerRecord })
    const learnerRecordTable = shallow(
      inner.instance().renderLearnerRecordTable(learnerRecord)
    )

    const logo = learnerRecordTable
      .find(".learner-record-inst-logo img")
      .first()

    assert.isTrue(logo.exists())
    assert.equal(logo.prop("src"), "/static/images/mit-black-logo.png")
    assert.equal(logo.prop("alt"), "MIT Logo")
  })
})
