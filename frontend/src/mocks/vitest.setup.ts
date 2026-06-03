import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { beforeAll, afterEach, afterAll } from 'vitest'
import { server } from './node'

beforeAll(() => server.listen())
afterEach(() => {
  cleanup()
  server.resetHandlers()
  localStorage.clear()
})
afterAll(() => server.close())
