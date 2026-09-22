export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public error_code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isNetworkError(): boolean {
    return this.status === 500 && this.error_code === "UNKNOWN_ERROR";
  }

  get isTimeout(): boolean {
    return this.status === 408;
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }
}
