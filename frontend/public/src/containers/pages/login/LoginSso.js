// @flow
import React, { useEffect } from "react"
import qs from "query-string"

const LoginSso = () => {
  useEffect(() => {
    const nextUrl =
      new URLSearchParams(window.location.search).get("next") ||
      window.location.pathname
    const params = qs.stringify({ next: nextUrl })

    window.location.href = `/login/?${params}`
  }, [])

  return (
    <div className="loading-container">
      <div>Redirecting to login...</div>
    </div>
  )
}

export default LoginSso
