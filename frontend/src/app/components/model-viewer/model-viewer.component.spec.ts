import { TestBed } from '@angular/core/testing';

import { ModelViewerComponent } from './model-viewer.component';
import { ApiService } from '../../services/api.service';

describe('ModelViewerComponent', () => {
  function createComponent() {
    TestBed.configureTestingModule({
      imports: [ModelViewerComponent],
      providers: [
        {
          provide: ApiService,
          useValue: {
            artifactUrl: (id: string, kind: string) => `/artifacts/${id}/${kind}`
          }
        }
      ]
    });
    return TestBed.createComponent(ModelViewerComponent).componentInstance;
  }

  it('shows an empty state before generation starts', () => {
    const component = createComponent();
    expect(component.overlayMessage).toBe('Waiting for a CAD prompt.');
  });

  it('shows running state while generation is active', () => {
    const component = createComponent();
    component.generation = {
      id: 'gen_1',
      conversation_id: 'conv_1',
      status: 'running',
      prompt: 'make a cube',
      assistant_summary: null,
      error: null,
      attempt_count: 1,
      artifacts: {
        step: false,
        glb: false,
        stl: false,
        native: false,
        script: false,
        log: false
      },
      created_at: 'now',
      updated_at: 'now'
    };

    expect(component.overlayMessage).toBe('Generating CAD model...');
  });

  it('builds a STEP artifact URL for the active generation', () => {
    const component = createComponent();
    component.generation = {
      id: 'gen_1',
      conversation_id: 'conv_1',
      status: 'succeeded',
      prompt: 'make a cube',
      assistant_summary: 'done',
      error: null,
      attempt_count: 1,
      artifacts: {
        step: true,
        glb: true,
        stl: false,
        native: false,
        script: true,
        log: true
      },
      created_at: 'now',
      updated_at: 'now'
    };

    expect(component.stepUrl()).toBe('/artifacts/gen_1/step');
  });
});
