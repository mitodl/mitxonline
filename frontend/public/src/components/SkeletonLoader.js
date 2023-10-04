import React from "react"
import ContentLoader from "react-content-loader"

const SkeletonLoader = props => (
  <ContentLoader
    width={305}
    height={229}
    viewBox="0 0 305 229"
    backgroundColor="#f0f0f0"
    foregroundColor="#dedede"
    {...props}
  >
    <rect x="0" y="150" rx="4" ry="4" width="271" height="9" />
    <rect x="0" y="170" rx="3" ry="3" width="119" height="6" />
    <rect x="0" y="0" rx="10" ry="10" width="303" height="142" />
  </ContentLoader>
)

export default SkeletonLoader
