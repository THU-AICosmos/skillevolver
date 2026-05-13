There's a news reader platform implemented in Next.js that is extremely slow and subscribers keep complaining about it. Some scenarios that subscribers have been complaining about:

- Bookmarking articles is slow
- Trends page is extremely slow on load time
- api responses are slower than expected

Your job is to use best practices to assess the root cause of the performance issues and fix them.
Use React and Next.js patterns and best practices and focus on API route optimization, bundle size reduction and excessive rendering.

The app must work properly:

- Homepage must show article feed data
- Bookmarking articles should work
- Trends page deep-dive tab must render properly (don't remove `data-testid="deepdive-content"`)

Constraints:

- Do not modify `data-testid` attributes or remove any component using them
- Do not remove `performance.mark()` calls from ArticleCard
