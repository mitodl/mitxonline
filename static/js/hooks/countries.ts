import { useSelector } from "react-redux"
import { useRequest } from "redux-query-react"
import { countriesQuery, countriesSelector } from "../lib/queries/users"

export default function useCountries() {
  const [state, forceRequestCountries] = useRequest(countriesQuery())
  const countries = useSelector(countriesSelector)
  return { countries, state, forceRequestCountries }
}
