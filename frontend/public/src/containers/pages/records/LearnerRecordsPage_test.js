// @flow
/* global SETTINGS: false */
import { assert } from "chai"

import LearnerRecordsPage, {
  LearnerRecordsPage as InnerLearnerRecordsPage
} from "./LearnerRecordsPage"
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

	assert.isTrue(inner.find(".std-page-header").exists())
	assert.include(inner.find(".std-page-header h1").text(), "Learner Records")
  })
})

