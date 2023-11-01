export type CoursePage = {
  featured_image_src: string,
  page_url: string,
  live: boolean,
}

export type InstructorPage = {
  id: number,
  instructor_name: string,
  isntructor_title: string,
  instructor_bio_short: string,
  instructor_bio_long: ?string,
  feature_image_src: string,
}

export type ProgramPage = {
  id: number,
  featured_image_src: string,
  page_url: string,
  live: boolean,
}
