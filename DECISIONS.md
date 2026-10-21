# Enrollment Review Workbench - Design Decisions



## 1. Product and UX decisions



I optimized for a predictable review workflow: identify submissions that need attention, understand the review reason, inspect relevant details, and record a decision safely. The queue displays applicant, employer group, product, requested coverage, submission date, review reason, and status. Search, filters, and sorting help reviewers find records efficiently.



The assignment does not define a custom priority formula. I use the mock API's supported sorting options rather than inventing a new scoring system. Returning a submission requires an explanatory note. The frontend uses API data instead of maintaining a separate hardcoded submission list.



## 2. Technical approach



The application uses React, TypeScript, and Vite. React manages the interface, TypeScript checks data and decision types, and Vite supports development and production builds. API requests are separated into a frontend API module, while the application manages review workflow state.



I used Node.js's built-in test runner for API integration tests to avoid adding a testing dependency for this time-constrained assignment. The Vite proxy forwards `/api` requests to the mock API.



## 3. Reliability and edge cases



The five integration tests cover applicant search, RETURN without a required note, successful approval and queue removal, retrying a transient failure, and a conflict caused by another reviewer. These cases address invalid decisions, stale queue data, temporary failures, and misleading success feedback.



Tests reset API state between cases and use a separate port from the development API. I deliberately left out authentication, a new backend, persistent storage, pagination, and a larger design system because they are outside the supplied scope.



## 4. Accessibility



The interface should communicate validation and decision outcomes through text rather than color alone. Clear labels, keyboard-operable controls, understandable loading states, and prevention of repeated submissions are important to this workflow.



Keyboard navigation, focus behavior after errors and decisions, screen-reader announcements, and responsive layouts still need systematic manual verification. I would address any gaps found rather than assume accessibility from appearance alone.



## 5. AI usage



I used ChatGPT for implementation guidance, debugging, test design, and edge-case review. I validated suggestions by running tests and quality checks instead of assuming generated output was correct.



During testing, the API readiness check initially used the wrong HTTP method for reset. After fixing it, an approval test still failed because it used a deliberately conflicting record. I separated the normal approval test from the conflict test and reran the suite. The latest reported checks were five passing integration tests, a successful lint run, and a successful production build.



## 6. If I had another day



I would add focused frontend tests for search, filtering, validation, loading states, and conflict messaging. I would systematically test keyboard-only use, focus management, screen-reader announcements, and different viewport sizes. I would also test malformed API responses and network failures before considering the workflow production-ready.
