import { useSelector } from "react-redux"
import { currentUserSelector } from "../lib/queries/users"
import { CurrentUser, LoggedInUser } from "../types/auth"

/**
 * Get the current user, an anonymous user, or null if not loaded yet
 */
export function useCurrentUser(): CurrentUser | null {
  return useSelector(currentUserSelector)
}

/**
 * Get the current user if logged in
 * @returns the current user if logged in
 */
export function useLoggedInUser(): LoggedInUser | null {
  const currentUser = useCurrentUser()

  return currentUser?.is_authenticated ? currentUser : null
}
