import { isUndefined } from "lodash"
import _truncate from "lodash/truncate"
import { Moment } from "moment"
import moment from "moment-timezone"
import qs from "query-string"
import * as R from "ramda"
import {
  all,
  complement,
  compose,
  curry,
  defaultTo,
  either,
  find,
  isEmpty,
  isNil,
  lensPath,
  trim,
  view
} from "ramda"
import { ActionPromiseValue } from "redux-query"
import { HttpRespErrorMessage } from "../types/http"

/**
 * Returns a promise which resolves after a number of milliseconds have elapsed
 */
export const wait = (millis: number): Promise<void> =>
  new Promise(resolve => setTimeout(resolve, millis))

/**
 * Adds on an index for each item in an iterable
 */
export function* enumerate<T>(
  iterable: Iterable<T>
): Generator<[number, T], void, void> {
  let i = 0

  for (const item of iterable) {
    yield [i, item]
    ++i
  }
}

export const isEmptyText = compose(isEmpty, trim, defaultTo(""))

export const notNil = complement(isNil)
export const firstNotNil = find(notNil)

export const goBackAndHandleEvent = curry((history, e) => {
  e.preventDefault()
  history.goBack()
})
export const preventDefaultAndInvoke = curry(
  (invokee: (...args: Array<any>) => any, e: Event) => {
    if (e) {
      e.preventDefault()
    }

    invokee()
  }
)

export const truncate = (
  text: string | null | undefined,
  length: number
): string =>
  text
    ? _truncate(text, {
      length:    length,
      separator: " "
    })
    : ""

export const getTokenFromUrl = (props: Record<string, any>): string => {
  const urlMatchPath = ["match", "params", "token"],
    querystringPath = ["location", "search"]
  let token = view(lensPath(urlMatchPath))(props)
  if (token) return token
  const querystring = view(lensPath(querystringPath))(props)
  const parsedQuerystring = qs.parse(querystring)
  token = parsedQuerystring.token
  return token || ""
}

export const removeTrailingSlash = (str: string) =>
  str.length > 0 && str[str.length - 1] === "/"
    ? str.substr(0, str.length - 1)
    : str

export const emptyOrNil = either(isEmpty, isNil)
export const allEmptyOrNil = all(emptyOrNil)
export const anyNil = R.any(R.isNil)

export const spaceSeparated = (
  strings: Array<string | null | undefined>
): string => strings.filter(str => str).join(" ")

export function* incrementer(): Generator<number, any, any> {
  let int = 1

  // eslint-disable-next-line no-constant-condition
  while (true) {
    yield int++
  }
}

export const toArray = (obj: any) =>
  Array.isArray(obj) ? obj : obj ? [obj] : undefined

export const objectToFormData = (object: Record<string, any>) => {
  const formData = new FormData()
  Object.entries(object).forEach(([k, v]) => {
    if (!isNil(v)) {
      formData.append(k, v)
    }
  })
  return formData
}

// Example return values: "January 1, 2019", "December 31, 2019"
export const formatPrettyDate = (momentDate: Moment) =>
  momentDate.format("MMMM D, YYYY")
export const formatPrettyDateTimeAmPm = (momentDate: Moment) =>
  momentDate.format("LLL")
export const formatPrettyDateTimeAmPmTz = (monthDate: Moment) =>
  monthDate.tz(moment.tz.guess()).format("LLL z")

export const firstItem = R.view(R.lensIndex(0))
export const secondItem = R.view(R.lensIndex(1))

export const parseDateString = (
  dateString: string | null | undefined
): Moment | null | undefined =>
  emptyOrNil(dateString) ? undefined : moment(dateString)

const getDateExtreme = R.curry(
  (
    compareFunc: (...args: Array<any>) => any,
    momentDates: Array<Moment | null | undefined>
  ): Moment | null | undefined => {
    const filteredDates = R.reject(R.isNil, momentDates)

    if (filteredDates.length === 0) {
      return null
    }

    return R.compose(moment, R.apply(compareFunc))(filteredDates)
  }
)

export const getMinDate = getDateExtreme(Math.min)
export const getMaxDate = getDateExtreme(Math.max)

export const newSetWith = (set: Set<any>, valueToAdd: any): Set<any> => {
  const newSet = new Set(set)
  newSet.add(valueToAdd)
  return newSet
}

export const newSetWithout = (set: Set<any>, valueToDelete: any): Set<any> => {
  const newSet = new Set(set)
  newSet.delete(valueToDelete)
  return newSet
}

export const parseIntOrUndefined = (value: any): number | null | undefined => {
  const parsed = parseInt(value)
  return isNaN(parsed) ? undefined : parsed
}

/**
 * Returns a Promise that executes a function after a given number of milliseconds then resolves
 */
export const timeoutPromise = (
  funcToExecute: (...args: Array<any>) => any,
  timeoutMs: number
): Promise<any> => {
  return new Promise(resolve =>
    setTimeout(() => {
      funcToExecute()
      resolve(null)
    }, timeoutMs)
  )
}

export const sameDayOrLater = (
  momentDate1: Moment,
  momentDate2: Moment
): boolean =>
  momentDate1.startOf("day").isSameOrAfter(momentDate2.startOf("day"))

export const isSuccessResponse = (
  response: ActionPromiseValue | undefined
): boolean =>
  !isUndefined(response) && response.status >= 200 && response.status < 300

export const isErrorResponse = (response: ActionPromiseValue): boolean =>
  (!isUndefined(response) && response.status === 0) || response.status >= 400

export const isUnauthorizedResponse = (response: ActionPromiseValue): boolean =>
  (!isUndefined(response) && response.status === 401) || response.status === 403

export const getErrorMessages = (
  response: ActionPromiseValue
): HttpRespErrorMessage => {
  if (!response.body || !response.body.errors) {
    return null
  }

  return response.body.errors
}
