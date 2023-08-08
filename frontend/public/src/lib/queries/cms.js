// @flow
import { nextState } from "./util"
import { pathOr } from "ramda"

export const instructorPageSelector = pathOr(null, [
  "entites",
  "instructorPage"
])

export const instructorPageQueryKey = "instructorPage"

export const instructorPageQuery = (pageId: any) => ({
  queryKey:  instructorPageQueryKey,
  url:       `/api/instructor/${pageId}/`,
  transform: json => ({
    instructorPage: json
  }),
  update: {
    instructorPage: nextState
  }
})
