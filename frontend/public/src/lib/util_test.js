// @flow
import sinon from "sinon"
import { assert } from "chai"
import moment from "moment"

import {
  wait,
  enumerate,
  isEmptyText,
  preventDefaultAndInvoke,
  notNil,
  firstNotNil,
  truncate,
  getTokenFromUrl,
  makeUUID,
  spaceSeparated,
  formatPrettyDate,
  firstItem,
  secondItem,
  getMinDate,
  getMaxDate,
  newSetWith,
  newSetWithout,
  timeoutPromise,
  isSuccessResponse,
  isErrorResponse,
  isUnauthorizedResponse,
  formatLocalePrice,
  intCheckFeatureFlag,
  getStartDateText
} from "./util"

describe("utility functions", () => {
  it("waits some milliseconds", done => {
    let executed = false
    wait(30).then(() => {
      executed = true
    })

    setTimeout(() => {
      assert.isFalse(executed)

      setTimeout(() => {
        assert.isTrue(executed)

        done()
      }, 20)
    }, 20)
  })

  it("enumerates an iterable", () => {
    const someNums = function* () {
      yield* [6, 7, 8, 9, 10]
    }

    const list = []
    for (const item of enumerate(someNums())) {
      list.push(item)
    }

    assert.deepEqual(list, [
      [0, 6],
      [1, 7],
      [2, 8],
      [3, 9],
      [4, 10]
    ])
  })

  it("isEmptyText works as expected", () => {
    [
      [" ", true],
      ["", true],
      ["\n\t   ", true],
      ["                   \t ", true],
      ["foo \n", false],
      ["foo", false],
      ["   \n\tfoo", false]
    ].forEach(([text, exp]) => {
      assert.equal(isEmptyText(text), exp)
    })
  })

  it("truncate works as expected", () => {
    [
      ["", ""],
      [null, ""],
      ["A random string", "A random string"],
      ["A random string with many words.", "A random string..."]
    ].forEach(([text, expected]) => {
      assert.equal(truncate(text, 20), expected)
    })
  })

  it("preventDefaultAndInvoke works as expected", () => {
    const invokee = sinon.stub()
    const event = {
      preventDefault: sinon.stub()
    }

    preventDefaultAndInvoke(invokee, event)

    sinon.assert.calledWith(invokee)
    sinon.assert.calledWith(event.preventDefault)
  })

  it("notNil works as expected", () => {
    [
      [null, false],
      [undefined, false],
      [0, true],
      ["", true],
      ["abc", true]
    ].forEach(([val, exp]) => {
      assert.equal(notNil(val), exp)
    })
  })

  it("firstNotNil works as expected", () => {
    [
      [["value"], "value"],
      [[null, undefined, "value"], "value"],
      [[null, 123, null], 123]
    ].forEach(([val, exp]) => {
      assert.equal(firstNotNil(val), exp)
    })
  })

  it("getTokenFromUrl gets a token value from a url match or the querystring", () => {
    [
      ["url_token", undefined, "url_token"],
      [undefined, "?token=querystring_token", "querystring_token"],
      ["url_token", "?token=querystring_token", "url_token"],
      [undefined, "?not_token=whatever", ""],
      [undefined, undefined, ""]
    ].forEach(([urlMatchTokenValue, querystringValue, exp]) => {
      const props = {
        match: {
          params: {
            token: urlMatchTokenValue
          }
        },
        location: {
          search: querystringValue
        }
      }
      const token = getTokenFromUrl(props)
      assert.equal(token, exp)
    })
  })

  describe("makeUUID", () => {
    it("should return a string", () => {
      const uuid = makeUUID(10)
      assert.isString(uuid)
    })

    it("should be as long as you specify", () => {
      [10, 11, 12, 20, 3].forEach(len => {
        assert.equal(makeUUID(len).length, len)
      })
    })

    it("it uhh shouldnt return the same thing twice :D", () => {
      assert.notEqual(makeUUID(10), makeUUID(10))
    })
  })

  describe("spaceSeparated", () => {
    it("should return a space separated string when given an array of strings or nulls", () => {
      [
        [["a", "b", "c"], "a b c"],
        [[null, null], ""],
        [[null, "a", "b"], "a b"],
        [["a", "b", null], "a b"]
      ].forEach(([inputArr, expectedStr]) => {
        assert.deepEqual(spaceSeparated(inputArr), expectedStr)
      })
    })
  })

  it("formatPrettyDate should return a formatted moment date", () => {
    moment.locale("en")
    const momentDate = moment("2019-01-01T00:00:00.000000")
    assert.equal(formatPrettyDate(momentDate), "January 1, 2019")
  })

  it("firstItem should return the first item of an array", () => {
    assert.equal(firstItem([1, 2, 3]), 1)
    assert.isUndefined(firstItem([]))
  })

  it("secondItem should return the second item of an array", () => {
    assert.equal(secondItem([1, 2, 3]), 2)
    assert.isUndefined(secondItem([]))
  })

  it("newSetWith returns a set with an additional item", () => {
    const set = new Set([1, 2, 3])
    assert.deepEqual(newSetWith(set, 3), set)
    assert.deepEqual(newSetWith(set, 4), new Set([1, 2, 3, 4]))
  })

  it("newSetWithout returns a set without a specified item", () => {
    const set = new Set([1, 2, 3])
    assert.deepEqual(newSetWithout(set, 3), new Set([1, 2]))
    assert.deepEqual(newSetWithout(set, 4), set)
  })

  it("timeoutPromise returns a Promise that executes a function after a delay then resolves", async () => {
    const func = sinon.stub()
    const promise = timeoutPromise(func, 10)
    sinon.assert.callCount(func, 0)
    await promise
    sinon.assert.callCount(func, 1)
  })

  describe("dateFunction", () => {
    const futureDate = moment().add(7, "days"),
      pastDate = moment().add(-7, "days"),
      now = moment()

    it("getMinDate returns the earliest date of a list of dates or null", () => {
      let dates = [futureDate, pastDate, now, now, undefined, null]
      assert.equal(getMinDate(dates).toISOString(), pastDate.toISOString())
      dates = [null, undefined]
      assert.isNull(getMinDate(dates))
    })

    it("getMaxDate returns the latest date of a list of dates or null", () => {
      let dates = [futureDate, pastDate, now, now, undefined, null]
      assert.equal(getMaxDate(dates).toISOString(), futureDate.toISOString())
      dates = [null, undefined]
      assert.isNull(getMaxDate(dates))
    })
  })

  //
  ;[
    [200, false],
    [299, false],
    [300, false],
    [400, true],
    [500, true]
  ].forEach(([status, expResult]) => {
    it(`isErrorResponse returns ${String(expResult)} when status=${String(
      status
    )}`, () => {
      const response = {
        status: status,
        body:   {}
      }
      assert.equal(isErrorResponse(response), expResult)
    })
  })

  //
  ;[
    [200, true],
    [299, true],
    [300, false],
    [400, false],
    [500, false]
  ].forEach(([status, expResult]) => {
    it(`isSuccessResponse returns ${String(expResult)} when status=${String(
      status
    )}`, () => {
      const response = {
        status: status,
        body:   {}
      }
      assert.equal(isSuccessResponse(response), expResult)
    })
  })

  //
  ;[
    [401, true],
    [403, true],
    [200, false],
    [400, false],
    [500, false]
  ].forEach(([status, expResult]) => {
    it(`isUnauthorizedResponse returns ${String(
      expResult
    )} when status=${String(status)}`, () => {
      const response = {
        status: status,
        body:   {}
      }
      assert.equal(isUnauthorizedResponse(response), expResult)
    })
  })

  describe("formatLocalePrice", () => {
    const testPrice = 512.25

    it("formatLocalePrice returns a US-formatted price string when the input is a number", () => {
      assert.equal(formatLocalePrice(testPrice), "$512.25")
    })

    it("formatLocalePrice returns a US-formatted price string equalling zero when the input is null", () => {
      assert.equal(formatLocalePrice(null), "$0.00")
    })

    it("formatLocalePrice returns a US-formatted price string equalling zero when the input is negative", () => {
      assert.equal(formatLocalePrice(null), "$0.00")
    })
  })

  describe("checkFeatureFlag", () => {
    const SETTINGS = {
      features: {
        test_flag:       true,
        other_test_flag: false
      }
    }

    const document = {
      location: new URL("https://example.com/?test=arg&flagtwo")
    }

    it("returns the flag setting if the feature flag is set", () => {
      assert.isTrue(
        intCheckFeatureFlag("test_flag", "anonymousUser", document, SETTINGS)
      )
      assert.isFalse(
        intCheckFeatureFlag(
          "other_test_flag",
          "anonymousUser",
          document,
          SETTINGS
        )
      )
      assert.isTrue(
        intCheckFeatureFlag("flagtwo", "anonymousUser", document, SETTINGS)
      )
    })
  })

  describe("getStartDateText", () => {
    [
      ["course", "past", false, "Started"],
      ["course run", "past", false, "Started"],
      ["course", "future", false, "Starts"],
      ["course run", "future", false, "Starts"],
      ["course", "past", true, "Start Anytime"],
      ["course run", "past", true, "Start Anytime"],
      ["course", "future", true, "Starts"],
      ["course run", "future", true, "Starts"]
    ].forEach(([coursewareType, startDatePosition, selfPaced, displayText]) => {
      it(`displays the ${displayText} text when the ${coursewareType} has a start date in the ${startDatePosition} and there ${
        selfPaced ? "are" : "are no"
      } self-paced courses`, () => {
        const course = {
          courseruns: [
            {
              start_date:
                startDatePosition === "future" ?
                  moment().add(1, "days") :
                  moment().subtract(1, "days"),
              is_self_paced: false
            }
          ]
        }

        if (selfPaced) {
          course["courseruns"][0]["is_self_paced"] = true
        }

        assert.isTrue(
          getStartDateText(
            coursewareType === "course" ? course : course["courseruns"][0]
          ).includes(displayText)
        )
      })
    })

    it("displays the earliest start date if there are multiple future start dates", () => {
      const startDates = [
        moment().add(1, "days"),
        moment().add(2, "days"),
        moment().add(3, "days")
      ]

      const course = {
        courseruns: [
          {
            start_date: startDates[0]
          },
          {
            start_date: startDates[1]
          },
          {
            start_date: startDates[2]
          }
        ]
      }

      assert.isTrue(getStartDateText(course).includes("Starts"))
      assert.isTrue(
        getStartDateText(course).includes(formatPrettyDate(startDates[0]))
      )
      assert.isFalse(
        getStartDateText(course).includes(formatPrettyDate(startDates[2]))
      )
    })

    it("displays the earliest start date if there are multiple past start dates", () => {
      const startDates = [
        moment().subtract(1, "days"),
        moment().subtract(2, "days"),
        moment().subtract(3, "days")
      ]

      const course = {
        courseruns: [
          {
            start_date: startDates[2]
          },
          {
            start_date: startDates[1]
          },
          {
            start_date: startDates[0]
          }
        ]
      }

      assert.isTrue(getStartDateText(course).includes("Started"))
      assert.isTrue(
        getStartDateText(course).includes(formatPrettyDate(startDates[2]))
      )
      assert.isFalse(
        getStartDateText(course).includes(formatPrettyDate(startDates[0]))
      )
    })
  })
})
