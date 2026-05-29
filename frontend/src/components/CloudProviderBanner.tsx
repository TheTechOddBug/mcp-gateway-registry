import React, { useEffect, useState } from 'react';
import axios from 'axios';

type Hint = 'on_premises' | 'other' | 'declined';

interface BannerState {
  should_show: boolean;
  last_cloud: string;
  last_detection_method: string;
  hint_set: boolean;
}

export const CloudProviderBanner: React.FC = () => {
  const [shouldShow, setShouldShow] = useState(false);

  useEffect(() => {
    axios
      .get<BannerState>('/api/registry/v0.1/banner-state')
      .then((res) => setShouldShow(res.data.should_show))
      .catch((err) => console.warn('Failed to fetch banner state:', err));
  }, []);

  const submit = async (hint: Hint) => {
    setShouldShow(false);
    try {
      await axios.post('/api/registry/v0.1/cloud-provider-hint', { hint });
    } catch (err: unknown) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined;
      if (status === 409) {
        console.warn('cloud-provider-hint already set (409); treating as success');
      } else {
        console.warn('cloud-provider-hint POST failed; rolling back banner', err);
        try {
          const res = await axios.get<BannerState>('/api/registry/v0.1/banner-state');
          setShouldShow(res.data.should_show);
        } catch {
          // ignore rollback fetch failure; banner stays hidden
        }
      }
    }
  };

  if (!shouldShow) return null;

  return (
    <div
      role="region"
      aria-label="Cloud provider confirmation"
      className="bg-yellow-50 border-l-4 border-yellow-400 p-4 my-4 mx-6"
    >
      <p className="text-sm font-medium text-gray-900">
        We tried 5 ways to detect your hosting environment and couldn't find one.
        Are you running this on-premises, or somewhere else?
      </p>
      <p className="text-xs text-gray-600 mt-1">
        If you're actually on AWS, Azure, or GCP, please upgrade to 1.24.2+&nbsp;&mdash; we likely have a detection bug for your setup.
      </p>
      <div className="flex gap-3 mt-3 items-center">
        <button
          type="button"
          onClick={() => submit('on_premises')}
          className="px-3 py-1 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          On-premises
        </button>
        <button
          type="button"
          onClick={() => submit('other')}
          className="px-3 py-1 bg-gray-200 text-gray-900 text-sm font-medium rounded hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          Other / not sure
        </button>
        <button
          type="button"
          onClick={() => submit('declined')}
          className="text-sm text-gray-600 hover:text-gray-900 underline focus:outline-none"
        >
          Don't show this again
        </button>
      </div>
      {!shouldShow && (
        <span className="sr-only" aria-live="polite">
          Banner dismissed.
        </span>
      )}
    </div>
  );
};

export default CloudProviderBanner;
