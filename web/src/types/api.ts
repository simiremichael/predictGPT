export interface ApiResponseMeta {
  page?: number;
  page_size?: number;
  total?: number;
  total_pages?: number;
  [key: string]: unknown;
}

export interface ApiSuccessResponse<T = unknown> {
  success: true;
  data: T;
  meta?: ApiResponseMeta;
}

export interface ApiErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export type ApiResponse<T = unknown> = ApiSuccessResponse<T> | ApiErrorResponse;

export function isApiError(res: ApiResponse): res is ApiErrorResponse {
  return res.success === false;
}
