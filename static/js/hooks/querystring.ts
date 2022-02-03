import qs from "query-string"
import { useLocation } from "react-router"

/**
 * Get the current querystring parsed out to an object
 * @returns a parsed querystring
 */
export default function useQueryString<
  Params extends { [K in keyof Params]?: string } = Record<string, string>
>(): Params {
  const { search } = useLocation()

  return qs.parse(search) as Params
}
