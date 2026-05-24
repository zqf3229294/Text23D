import { CommonModule } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  NgZone,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild
} from '@angular/core';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';

import { Generation } from '../../models';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-model-viewer',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './model-viewer.component.html',
  styleUrl: './model-viewer.component.css'
})
export class ModelViewerComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() generation: Generation | null = null;
  @ViewChild('canvasHost', { static: true }) canvasHost!: ElementRef<HTMLDivElement>;

  loading = false;
  loadError = '';

  private renderer?: THREE.WebGLRenderer;
  private scene?: THREE.Scene;
  private camera?: THREE.PerspectiveCamera;
  private controls?: OrbitControls;
  private resizeObserver?: ResizeObserver;
  private modelRoot?: THREE.Object3D;
  private animationFrame = 0;
  private loadedPreviewKey = '';

  constructor(
    private readonly api: ApiService,
    private readonly zone: NgZone
  ) {}

  ngAfterViewInit(): void {
    this.initScene();
    this.tryLoadGeneration();
  }

  ngOnChanges(_changes: SimpleChanges): void {
    this.tryLoadGeneration();
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.animationFrame);
    this.resizeObserver?.disconnect();
    this.disposeModel();
    this.controls?.dispose();
    this.renderer?.dispose();
  }

  get overlayMessage(): string {
    if (this.loadError) {
      return this.loadError;
    }
    if (this.loading) {
      return 'Loading preview...';
    }
    if (!this.generation) {
      return 'Waiting for a CAD prompt.';
    }
    if (this.generation.status === 'queued') {
      return 'Queued for generation.';
    }
    if (this.generation.status === 'running') {
      return 'Generating CAD model...';
    }
    if (this.generation.status === 'failed') {
      return 'Generation failed.';
    }
    if (this.generation.status === 'succeeded' && !this.modelRoot) {
      return 'Preview is not available.';
    }
    return '';
  }

  resetView(): void {
    if (!this.camera || !this.controls) {
      return;
    }
    this.frameObject(this.modelRoot ?? undefined);
  }

  stepUrl(): string {
    return this.generation ? this.api.artifactUrl(this.generation.id, 'step') : '#';
  }

  private initScene(): void {
    const host = this.canvasHost.nativeElement;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x11151d);

    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
    this.camera.position.set(90, 70, 110);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;

    const hemi = new THREE.HemisphereLight(0xf7fbff, 0x252018, 1.7);
    const key = new THREE.DirectionalLight(0xffffff, 2.5);
    key.position.set(90, 120, 80);
    key.castShadow = true;
    const fill = new THREE.DirectionalLight(0x9fd9ff, 0.75);
    fill.position.set(-80, 70, -120);
    this.scene.add(hemi, key, fill);

    const grid = new THREE.GridHelper(180, 18, 0x59606b, 0x303743);
    grid.position.y = -0.1;
    this.scene.add(grid);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(host);
    this.resize();

    this.zone.runOutsideAngular(() => this.animate());
  }

  private animate = (): void => {
    this.animationFrame = requestAnimationFrame(this.animate);
    this.controls?.update();
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  };

  private resize(): void {
    if (!this.renderer || !this.camera) {
      return;
    }
    const host = this.canvasHost.nativeElement;
    const width = Math.max(host.clientWidth, 1);
    const height = Math.max(host.clientHeight, 1);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  private tryLoadGeneration(): void {
    if (!this.renderer || !this.scene || !this.generation) {
      return;
    }
    const generation = this.generation;
    const preview = this.previewForGeneration(generation);
    if (
      generation.status !== 'succeeded' ||
      !preview ||
      preview.key === this.loadedPreviewKey
    ) {
      return;
    }
    this.loadGeneration(generation, preview);
  }

  private loadGeneration(
    generation: Generation,
    preview: { kind: 'glb' | 'stl'; key: string; url: string }
  ): void {
    this.loading = true;
    this.loadError = '';

    if (preview.kind === 'glb') {
      const loader = new GLTFLoader();
      loader.load(
        preview.url,
        (gltf) => this.acceptLoadedObject(gltf.scene, preview.key),
        undefined,
        () => {
          this.loading = false;
          this.loadError = 'The generated GLB could not be loaded.';
        }
      );
      return;
    }

    const loader = new STLLoader();
    loader.load(
      preview.url,
      (geometry) => {
        geometry.computeVertexNormals();
        const material = new THREE.MeshStandardMaterial({
          color: 0xaab4bd,
          roughness: 0.72,
          metalness: 0.08
        });
        const mesh = new THREE.Mesh(geometry, material);
        this.acceptLoadedObject(mesh, preview.key);
      },
      undefined,
      () => {
        this.loading = false;
        this.loadError = 'The generated STL preview could not be loaded.';
      }
    );
  }

  private acceptLoadedObject(object: THREE.Object3D, previewKey: string): void {
    this.disposeModel();
    this.modelRoot = object;
    this.modelRoot.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });
    this.scene?.add(this.modelRoot);
    this.loadedPreviewKey = previewKey;
    this.loading = false;
    this.frameObject(this.modelRoot);
  }

  private previewForGeneration(
    generation: Generation
  ): { kind: 'glb' | 'stl'; key: string; url: string } | null {
    const version = encodeURIComponent(generation.updated_at);
    if (generation.artifacts.glb) {
      return {
        kind: 'glb',
        key: `${generation.id}:glb:${generation.updated_at}`,
        url: `${this.api.artifactUrl(generation.id, 'glb')}?v=${version}`
      };
    }
    if (generation.artifacts.stl) {
      return {
        kind: 'stl',
        key: `${generation.id}:stl:${generation.updated_at}`,
        url: `${this.api.artifactUrl(generation.id, 'stl')}?v=${version}`
      };
    }
    return null;
  }

  private frameObject(object?: THREE.Object3D): void {
    if (!this.camera || !this.controls) {
      return;
    }
    if (!object) {
      this.camera.position.set(90, 70, 110);
      this.controls.target.set(0, 0, 0);
      this.controls.update();
      return;
    }

    const box = new THREE.Box3().setFromObject(object);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    object.position.sub(center);

    const maxDim = Math.max(size.x, size.y, size.z, 20);
    const distance = maxDim * 2.1;
    this.camera.near = Math.max(maxDim / 200, 0.1);
    this.camera.far = maxDim * 200;
    this.camera.position.set(distance, distance * 0.72, distance);
    this.camera.updateProjectionMatrix();
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  private disposeModel(): void {
    if (!this.modelRoot || !this.scene) {
      return;
    }
    this.scene.remove(this.modelRoot);
    this.modelRoot.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.geometry.dispose();
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        for (const material of materials) {
          material.dispose();
        }
      }
    });
    this.modelRoot = undefined;
    this.loadedPreviewKey = '';
  }
}
