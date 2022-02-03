import { assert } from "chai"
import { ReactWrapper, ShallowWrapper } from "enzyme"

export const assertRaises = async (
  asyncFunc: (...args: Array<any>) => any,
  expectedMessage: string
) => {
  let exception = null

  try {
    await asyncFunc()
  } catch (ex) {
    exception = ex as Error
  }

  if (!exception) {
    throw new Error("No exception caught")
  }

  assert.equal(exception.message, expectedMessage)
}
export const findFormikFieldByName = (
  wrapper: ShallowWrapper | ReactWrapper,
  name: string
): ShallowWrapper | ReactWrapper =>
  wrapper
    .find("FormikConnect(FieldInner)")
    .filterWhere(node => node.prop("name") === name)

export const findFormikErrorByName = (
  wrapper: ShallowWrapper | ReactWrapper,
  name: string
): ShallowWrapper | ReactWrapper =>
  wrapper
    .find("FormikConnect(ErrorMessageImpl)")
    .filterWhere(node => node.prop("name") === name)

export const shouldIf = (tf: boolean) => (tf ? "should" : "should not")
export const shouldIfGt0 = (num: number) => shouldIf(num > 0)
export const isIf = (tf: boolean) => (tf ? "is" : "is not")
